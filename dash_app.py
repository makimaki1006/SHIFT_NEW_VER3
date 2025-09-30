"""Dash application for ShiftSuite multi-tenant dashboard."""
from __future__ import annotations

import base64
from binascii import Error as BinasciiError
import io
import threading
import time
import uuid
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

SUMMARY5_COLUMNS: tuple[str, ...] = ("need", "upper", "staff", "lack", "excess")
SUMMARY5_LOWER = {name.lower() for name in SUMMARY5_COLUMNS}
MAX_SESSIONS = 128


@dataclass
class HeatmapSettings:
    """Container for heatmap display settings."""

    zmax_default: float = 10.0
    quantiles: Dict[str, float] = field(
        default_factory=lambda: {"p90": 10.0, "p95": 10.0, "p99": 10.0}
    )


@dataclass
class SessionData:
    """Data container stored for each browser session."""

    heat_staff: pd.DataFrame
    heat_ratio: pd.DataFrame
    shortage_time: pd.DataFrame
    shortage_ratio: pd.DataFrame
    heat_settings: HeatmapSettings
    kpi_lack_h: Optional[float] = None
    jain_index: Optional[float] = None
    source_filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def metadata(self) -> dict:
        shortage_time_dates = [str(col) for col in self.shortage_time.columns]
        shortage_ratio_dates = [str(col) for col in self.shortage_ratio.columns]
        return {
            "status": "ready",
            "token": str(uuid.uuid4()),
            "filename": self.source_filename,
            "timestamp": self.created_at,
            "zmax_default": self.heat_settings.zmax_default,
            "zmax_quantiles": self.heat_settings.quantiles,
            "has_ratio": not self.heat_ratio.empty,
            "shortage_time_dates": shortage_time_dates,
            "shortage_time_default": shortage_time_dates[0] if shortage_time_dates else None,
            "shortage_ratio_dates": shortage_ratio_dates,
            "shortage_ratio_default": shortage_ratio_dates[0] if shortage_ratio_dates else None,
            "kpi_lack_h": self.kpi_lack_h,
            "jain_index": self.jain_index,
        }


SESSION_REGISTRY: "OrderedDict[str, SessionData]" = OrderedDict()
SESSION_LOCK = threading.Lock()


def register_session(session_id: str, data: SessionData) -> dict:
    """Store session data and keep registry bounded."""

    with SESSION_LOCK:
        SESSION_REGISTRY[session_id] = data
        SESSION_REGISTRY.move_to_end(session_id)
        while len(SESSION_REGISTRY) > MAX_SESSIONS:
            SESSION_REGISTRY.popitem(last=False)
    return data.metadata()


def get_session(session_id: str | None) -> Optional[SessionData]:
    if not session_id:
        return None
    with SESSION_LOCK:
        return SESSION_REGISTRY.get(session_id)


def drop_summary_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    normalized = pd.Index(map(lambda c: str(c).strip().lower(), df.columns))
    keep_mask = ~normalized.isin(SUMMARY5_LOWER)
    return df.loc[:, keep_mask]


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 14},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=40))
    return fig


def _get_column_series_by_str(df: pd.DataFrame, column_key: str) -> Optional[pd.Series]:
    for actual_column in df.columns:
        if str(actual_column) == column_key:
            return df[actual_column]
    return None


def _find_member(zf: zipfile.ZipFile, filename: str) -> Optional[str]:
    target = filename.lower()
    for info in zf.infolist():
        if info.is_dir():
            continue
        if Path(info.filename).name.lower() == target:
            return info.filename
    return None


def _read_excel_from_zip(
    zf: zipfile.ZipFile,
    filename: str,
    *,
    index_col: Optional[int] = 0,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    member = _find_member(zf, filename)
    if member is None:
        return pd.DataFrame()
    with zf.open(member) as file_obj:
        return pd.read_excel(file_obj, index_col=index_col, sheet_name=sheet_name)


def _calculate_heatmap_settings(heat_staff: pd.DataFrame) -> HeatmapSettings:
    settings = HeatmapSettings()
    if heat_staff.empty:
        return settings
    numeric = heat_staff.apply(pd.to_numeric, errors="coerce")
    positives = numeric[numeric > 0].stack().dropna()
    if positives.empty:
        return settings
    quantiles = {
        "p90": float(positives.quantile(0.90)),
        "p95": float(positives.quantile(0.95)),
        "p99": float(positives.quantile(0.99)),
    }
    settings.quantiles.update(quantiles)
    settings.zmax_default = max(10.0, min(50.0, quantiles["p95"]))
    return settings


def _build_ratio_frame(heat_staff: pd.DataFrame, heat_all: pd.DataFrame) -> pd.DataFrame:
    if heat_staff.empty or heat_all.empty or "need" not in heat_all.columns:
        return pd.DataFrame()
    need_series = heat_all["need"].replace(0, np.nan)
    ratio = heat_staff.divide(need_series, axis=0)
    ratio = ratio.clip(lower=0, upper=2)
    return ratio.fillna(0)


def load_session_data_from_zip(contents: str, filename: str | None) -> SessionData:
    if not contents:
        raise ValueError("ファイルの内容が空です。")
    try:
        header, encoded = contents.split(",", 1)
    except ValueError as exc:
        raise ValueError("不正なアップロードデータです。") from exc
    if "zip" not in header:
        raise ValueError("ZIPファイルをアップロードしてください。")

    try:
        decoded = base64.b64decode(encoded)
    except (BinasciiError, ValueError) as exc:
        raise ValueError("ZIPファイルのデコードに失敗しました。") from exc

    with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
        heat_all_df = _read_excel_from_zip(zf, "heat_ALL.xlsx", index_col=0)
        if heat_all_df.empty:
            raise ValueError("ZIP内に heat_ALL.xlsx が見つかりません。")

        heat_staff = drop_summary_columns(heat_all_df)
        heat_settings = _calculate_heatmap_settings(heat_staff)
        ratio_df = _build_ratio_frame(heat_staff, heat_all_df)

        shortage_time_df = _read_excel_from_zip(zf, "shortage_time.xlsx", index_col=0)
        shortage_ratio_df = _read_excel_from_zip(zf, "shortage_ratio.xlsx", index_col=0)

        shortage_role_df = _read_excel_from_zip(zf, "shortage_role.xlsx")
        kpi_lack_h = None
        if not shortage_role_df.empty and "lack_h" in shortage_role_df:
            try:
                kpi_lack_h = float(pd.to_numeric(shortage_role_df["lack_h"], errors="coerce").sum())
            except Exception:
                kpi_lack_h = None

        fairness_df = _read_excel_from_zip(
            zf, "fairness_before.xlsx", index_col=0, sheet_name="meta_summary"
        )
        jain_index = None
        if not fairness_df.empty and "metric" in fairness_df and "value" in fairness_df:
            row = fairness_df[fairness_df["metric"] == "jain_index"]
            if not row.empty:
                try:
                    jain_index = float(row["value"].iloc[0])
                except Exception:
                    jain_index = None

    return SessionData(
        heat_staff=heat_staff,
        heat_ratio=ratio_df,
        shortage_time=shortage_time_df,
        shortage_ratio=shortage_ratio_df,
        heat_settings=heat_settings,
        kpi_lack_h=kpi_lack_h,
        jain_index=jain_index,
        source_filename=filename,
    )


def _upload_section() -> html.Div:
    return html.Div(
        [
            html.H4("📊 ダッシュボード (ZIP アップロード)", className="mb-2"),
            html.P("out フォルダを ZIP 圧縮してアップロードしてください。"),
            dcc.Upload(
                id="zip-uploader",
                children=html.Div(["ドラッグ & ドロップ、またはクリックしてファイルを選択"]),
                multiple=False,
                className="border border-secondary p-4 rounded bg-light text-center",
            ),
            html.Div(id="upload-status", className="mt-3"),
        ],
        className="mb-4",
    )


def _navigation_bar() -> html.Div:
    return html.Div(
        [
            dcc.Link("Overview", href="/", className="nav-link me-3"),
            dcc.Link("Heatmap", href="/heat", className="nav-link me-3"),
            dcc.Link("Shortage", href="/short", className="nav-link me-3"),
        ],
        className="d-flex flex-wrap p-2 bg-light border-bottom mb-3",
    )


def page_overview(session: SessionData) -> html.Div:
    cards: list[html.Div] = []
    if session.kpi_lack_h is not None:
        cards.append(
            html.Div(
                [
                    html.H6("不足時間 (h)", className="card-title"),
                    html.H2(f"{session.kpi_lack_h:.1f}", className="card-text"),
                ],
                className="card p-3 me-3 mb-3",
            )
        )
    if session.jain_index is not None:
        cards.append(
            html.Div(
                [
                    html.H6("夜勤 Jain 指数", className="card-title"),
                    html.H2(f"{session.jain_index:.3f}", className="card-text"),
                ],
                className="card p-3 me-3 mb-3",
            )
        )
    if not cards:
        cards.append(html.Div("KPI データがありません", className="p-3"))

    filename_label = session.source_filename or "(ファイル名未設定)"
    return html.Div(
        [
            html.H3("Overview"),
            html.P(f"データソース: {filename_label}"),
            html.Div(cards, className="d-flex flex-wrap"),
        ]
    )


def page_heat(session: SessionData, metadata: Optional[dict]) -> html.Div:
    if session.heat_staff.empty:
        return html.Div(
            [
                html.H4("Heatmap Data Not Found"),
                html.P("ZIPファイルに heat_ALL.xlsx が含まれているか確認してください。"),
            ]
        )

    slider_default = metadata.get("zmax_default") if metadata else session.heat_settings.zmax_default
    shortage_dates = metadata.get("shortage_time_dates") if metadata else [str(col) for col in session.shortage_time.columns]
    shortage_default = metadata.get("shortage_time_default") if metadata else (shortage_dates[0] if shortage_dates else None)

    ratio_disabled = session.heat_ratio.empty
    ratio_option = {"label": "Ratio (staff ÷ need)", "value": "ratio", "disabled": ratio_disabled}

    return html.Div(
        [
            html.Div(
                [
                    dcc.RadioItems(
                        id="hm-mode-radio",
                        options=[
                            {"label": "Raw 人数", "value": "raw"},
                            ratio_option,
                        ],
                        value="raw",
                        inline=True,
                        className="me-3",
                    ),
                    dcc.Dropdown(
                        id="hm-zmax-mode",
                        options=[
                            {"label": "Manual", "value": "manual"},
                            {"label": "90th %tile", "value": "p90"},
                            {"label": "95th %tile", "value": "p95"},
                            {"label": "99th %tile", "value": "p99"},
                        ],
                        value="manual",
                        clearable=False,
                        style={"width": "160px"},
                        className="me-2",
                    ),
                    html.Label("カラースケール上限 (zmax):", className="me-2"),
                    dcc.Slider(
                        id="hm-zmax-slider",
                        min=5,
                        max=50,
                        step=1,
                        value=slider_default,
                        tooltip={"placement": "bottom", "always_visible": True},
                        className="flex-grow-1",
                    ),
                ],
                className="d-flex align-items-center mb-3 p-2 border rounded bg-light flex-wrap",
            ),
            dcc.Graph(id="hm-main-graph"),
            html.Hr(),
            html.H4("時間帯別不足人数 (選択日)"),
            dcc.Dropdown(
                id="hm-shortage-date-dropdown",
                options=[{"label": date, "value": date} for date in shortage_dates],
                value=shortage_default,
                style={"width": "320px"},
                className="mb-2",
            ),
            dcc.Graph(id="hm-shortage-bar-graph"),
        ]
    )


def page_shortage(session: SessionData, metadata: Optional[dict]) -> html.Div:
    if session.shortage_ratio.empty:
        return html.Div(
            [
                html.H4("Shortage Ratio Data Not Found"),
                html.P("ZIP内の shortage_ratio.xlsx を確認してください。"),
            ]
        )

    ratio_dates = metadata.get("shortage_ratio_dates") if metadata else [str(col) for col in session.shortage_ratio.columns]
    ratio_default = metadata.get("shortage_ratio_default") if metadata else (ratio_dates[0] if ratio_dates else None)

    heatmap = px.imshow(
        session.shortage_ratio,
        aspect="auto",
        color_continuous_scale=px.colors.sequential.OrRd,
        zmin=0,
        zmax=1,
        labels=dict(x="Date", y="Time", color="Shortage Ratio"),
    )

    return html.Div(
        [
            html.H3("Shortage Ratio Heatmap"),
            dcc.Graph(id="shortage-ratio-heatmap", figure=heatmap),
            html.Hr(),
            html.H4("Time Slot Shortage Ratio"),
            dcc.Dropdown(
                id="shortage-ratio-date-dropdown",
                options=[{"label": date, "value": date} for date in ratio_dates],
                value=ratio_default,
                style={"width": "320px"},
                className="mb-2",
            ),
            dcc.Graph(id="shortage-ratio-bar-graph"),
        ]
    )


def serve_layout() -> html.Div:
    session_id = str(uuid.uuid4())
    return html.Div(
        [
            dcc.Store(id="session-id", storage_type="session", data=session_id),
            dcc.Store(id="session-metadata", storage_type="session", data={"status": "empty"}),
            dcc.Location(id="url", refresh=False),
            _navigation_bar(),
            html.Div(
                [
                    _upload_section(),
                    html.Div(id="page-content", className="container-fluid p-3"),
                ],
                className="container-fluid",
            ),
        ]
    )


app: Dash = dash.Dash(__name__, suppress_callback_exceptions=True, title="ShiftSuite Dashboard")
app.layout = serve_layout
server = app.server


@app.callback(
    Output("upload-status", "children"),
    Output("session-metadata", "data"),
    Input("zip-uploader", "contents"),
    State("zip-uploader", "filename"),
    State("session-id", "data"),
    prevent_initial_call=True,
)
def handle_upload(contents: str | None, filename: str | None, session_id: str | None):
    if not contents or not session_id:
        raise PreventUpdate
    try:
        session_data = load_session_data_from_zip(contents, filename)
    except ValueError as exc:
        message = html.Div(str(exc), className="alert alert-danger")
        metadata = {"status": "error", "message": str(exc), "token": str(uuid.uuid4())}
        return message, metadata

    metadata = register_session(session_id, session_data)
    status = html.Div(
        [
            html.Strong("アップロード完了"),
            html.Span(f" : {session_data.source_filename}" if session_data.source_filename else ""),
        ],
        className="alert alert-success",
    )
    return status, metadata


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("session-metadata", "data"),
    State("session-id", "data"),
)
def route(pathname: str, metadata: dict | None, session_id: str | None):
    session_data = get_session(session_id)
    if session_data is None:
        return html.Div(
            [
                html.H3("データ未読み込み"),
                html.P("ZIPファイルをアップロードすると各種ページが表示されます。"),
            ],
            className="alert alert-info",
        )

    metadata = metadata or {}
    if pathname == "/heat":
        return page_heat(session_data, metadata)
    if pathname == "/short":
        return page_shortage(session_data, metadata)
    return page_overview(session_data)


@app.callback(
    Output("hm-main-graph", "figure"),
    Output("hm-zmax-slider", "disabled"),
    Output("hm-zmax-slider", "value"),
    Input("hm-mode-radio", "value"),
    Input("hm-zmax-slider", "value"),
    Input("hm-zmax-mode", "value"),
    State("session-id", "data"),
)
def update_heatmap(mode: str, slider_value: float, zmode: str, session_id: str | None):
    session_data = get_session(session_id)
    if session_data is None:
        return _empty_figure("データが読み込まれていません"), True, slider_value

    if mode == "raw":
        heat_df = session_data.heat_staff
        if heat_df.empty:
            return _empty_figure("heat_ALL.xlsx のデータがありません"), True, slider_value
        if zmode != "manual":
            slider_value = session_data.heat_settings.quantiles.get(zmode, session_data.heat_settings.zmax_default)
        slider_disabled = zmode != "manual"
        fig = px.imshow(
            heat_df,
            aspect="auto",
            color_continuous_scale=px.colors.sequential.YlOrRd,
            zmin=0,
            zmax=slider_value,
            labels=dict(x="日付", y="時間帯", color="配置人数"),
        )
        return fig, slider_disabled, slider_value

    ratio_df = session_data.heat_ratio
    if ratio_df.empty:
        return _empty_figure("Ratioデータが利用できません"), True, slider_value
    fig = px.imshow(
        ratio_df,
        aspect="auto",
        color_continuous_scale=px.colors.sequential.RdBu_r,
        zmin=0,
        zmax=2,
        labels=dict(x="日付", y="時間帯", color="充足率 (実績/必要)"),
    )
    return fig, True, slider_value


@app.callback(
    Output("hm-shortage-bar-graph", "figure"),
    Input("hm-shortage-date-dropdown", "value"),
    State("session-id", "data"),
)
def update_shortage_bar(selected_date: str | None, session_id: str | None):
    session_data = get_session(session_id)
    if session_data is None or selected_date is None:
        return _empty_figure("日付を選択してください")
    shortage_df = session_data.shortage_time
    if shortage_df.empty:
        return _empty_figure("該当する不足データがありません")
    series = _get_column_series_by_str(shortage_df, selected_date)
    if series is None:
        return _empty_figure("該当する不足データがありません")
    fig = px.bar(
        x=series.index,
        y=series.values,
        labels={"x": "時間帯", "y": "不足人数"},
        title=f"{selected_date} の時間帯別不足人数",
    )
    fig.update_layout(showlegend=False, xaxis_tickangle=-45, height=350)
    return fig


@app.callback(
    Output("shortage-ratio-bar-graph", "figure"),
    Input("shortage-ratio-date-dropdown", "value"),
    State("session-id", "data"),
)
def update_shortage_ratio_bar(selected_date: str | None, session_id: str | None):
    session_data = get_session(session_id)
    if session_data is None or selected_date is None:
        return _empty_figure("日付を選択してください")
    ratio_df = session_data.shortage_ratio
    if ratio_df.empty:
        return _empty_figure("該当する不足率データがありません")
    series = _get_column_series_by_str(ratio_df, selected_date)
    if series is None:
        return _empty_figure("該当する不足率データがありません")
    fig = px.bar(
        x=series.index,
        y=series.values,
        labels={"x": "時間帯", "y": "不足率"},
        title=f"{selected_date} の時間帯別不足率",
    )
    fig.update_layout(showlegend=False, xaxis_tickangle=-45, height=350)
    return fig


if __name__ == "__main__":
    app.run_server(debug=True, port=8055)
