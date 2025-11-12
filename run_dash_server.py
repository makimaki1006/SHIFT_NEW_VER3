#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dash Server Launcher for E2E Testing
Starts the Dash application on port 8055 for Playwright E2E tests.
"""

import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("Dash起動中 (E2E テスト用)...")
print("ブラウザでアクセス: http://127.0.0.1:8055")

# Import dash and create independent app instance for E2E testing
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_app

# Create independent app instance (not using dash_app.app)
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Import COLOR_SCHEMES for UI
COLOR_SCHEMES = dash_app.COLOR_SCHEMES
DEFAULT_COLOR_SCHEME = dash_app.DEFAULT_COLOR_SCHEME

# ============================================================
# タブ表示名マッピング（Phase 1 Task 1.1）
# ============================================================
# 内部値（ルーティングキー）と表示名（日本語+絵文字）のマッピング
TAB_DISPLAY_NAMES = {
    'overview': ('📊 概要', '概要タブに移動'),
    'heatmap': ('🔥 ヒートマップ', 'ヒートマップタブに移動'),
    'shortage': ('⚠️ 不足分析', '不足分析タブに移動'),
    'individual': ('👤 職員個別分析', '職員個別分析タブに移動'),
    'team': ('👥 チーム分析', 'チーム分析タブに移動'),
    'fatigue': ('😴 疲労分析', '疲労分析タブに移動'),
    'leave': ('🏖️ 休暇分析', '休暇分析タブに移動'),
    'fairness': ('⚖️ 公平性', '公平性タブに移動'),
    'optimization': ('⚡ 最適化分析', '最適化分析タブに移動'),
    # Phase 3.1: 以下のタブは品質問題により一時的に無効化（将来改善予定）
    # 'forecast': ('📈 需要予測', '需要予測タブに移動'),  # 理由: 精度が悪い
    'hire-plan': ('👷 採用計画', '採用計画タブに移動'),
    'cost': ('💰 コスト分析', 'コスト分析タブに移動'),
    'gap-analysis': ('📋 基準乖離分析', '基準乖離分析タブに移動'),
    'blueprint': ('🧠 作成ブループリント', '作成ブループリントタブに移動'),
    # 'logic': ('🔍 ロジック解明', 'ロジック解明タブに移動'),  # 理由: 表示不良 + ロジック怪しい
    # 'ai-analysis': ('🤖 AI分析', 'AI分析タブに移動'),  # 理由: 表示不良 + ロジック怪しい
    # 'summary': ('📊 サマリー', 'サマリータブに移動'),  # 理由: 表示不良 + 他タブと重複
    # 'reports': ('📄 レポート', 'レポートタブに移動'),  # 理由: 表示不良 + PPT生成物品質低
}

# タブの内部値リスト（ルーティングで使用される順序）
TAB_KEYS = [
    'overview', 'heatmap', 'shortage', 'individual', 'team',
    'fatigue', 'leave', 'fairness', 'optimization',
    # Phase 3.1: 品質問題により一時無効化: 'forecast', 'logic', 'ai-analysis', 'summary', 'reports'
    'hire-plan', 'cost', 'gap-analysis', 'blueprint'
]

# NOTE: Using independent app instance for E2E testing.
# Shortage callbacks will be registered separately via register_shortage_callbacks().

# Define basic layout with accessibility (Phase 3-3)
app.layout = html.Div([
    html.H2("ShiftSuite Multi-tenant Dashboard", **{'aria-level': '1'}),

    # Upload component
    dcc.Upload(
        id='zip-uploader',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select ZIP File')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=False
    ),

    # Session info (also defined in dash_app.py for standalone mode)
    dcc.Store(id='session-id'),
    dcc.Store(id='session-metadata'),

    # Phase 3-5: Color Scheme Selection
    dcc.Store(id='selected-color-scheme', data=DEFAULT_COLOR_SCHEME),
    html.Div([
        html.Label('カラースキーム選択:', style={'fontWeight': 'bold', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='color-scheme-dropdown',
            options=[
                {'label': scheme_data['name'], 'value': scheme_key}
                for scheme_key, scheme_data in COLOR_SCHEMES.items()
            ],
            value=DEFAULT_COLOR_SCHEME,
            clearable=False,
            style={'width': '300px'}
        )
    ], style={'margin': '10px', 'display': 'flex', 'alignItems': 'center'}, id='color-scheme-selector'),

    # Scenario Selection (旧システム完全復旧のための必須機能)
    html.Div([
        html.Label('シナリオ選択:', style={'fontWeight': 'bold', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='scenario-dropdown',
            options=[],
            value=None,
            clearable=False,
            style={'width': '300px'},
            placeholder='ZIPファイルをアップロードしてください'
        )
    ], style={'margin': '10px', 'display': 'flex', 'alignItems': 'center'}, id='scenario-selector'),

    # Navigation tabs (will be populated after upload)
    html.Div(id='nav-tabs', **{'aria-live': 'polite'}),

    # Tab selector store
    dcc.Store(id='selected-tab', data='overview'),

    # Tab content
    html.Div(id='tab-content', role="main", **{'aria-live': 'polite', 'aria-label': 'メインコンテンツ'}),

    # Hidden div for storing upload status
    html.Div(id='upload-output', style={'display': 'none'}, **{'aria-hidden': 'true'}),
], role="application")

# シナリオ名の日本語マッピング（旧システム完全復旧のため）
SCENARIO_DISPLAY_NAMES = {
    'out_mean_based': '平均値ベース',
    'out_median_based': '中央値ベース',
    'out_p25_based': '25パーセンタイルベース'
}

# Upload callback - シナリオドロップダウンのオプションも返す
@app.callback(
    [Output('session-id', 'data'),
     Output('session-metadata', 'data'),
     Output('scenario-dropdown', 'options'),
     Output('scenario-dropdown', 'value'),
     Output('nav-tabs', 'children'),
     Output('upload-output', 'children')],
    [Input('zip-uploader', 'contents')],
    [State('zip-uploader', 'filename')]
)
def handle_upload(contents, filename):
    if contents is None:
        return None, None, [], None, None, None

    try:
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Load session data using dash_app module
        session = dash_app.load_session_data_from_zip(contents, filename)
        dash_app.register_session(session_id, session)

        # Get metadata
        metadata = session.metadata()

        # シナリオオプションを生成（旧システム完全復旧のため）
        available_scenarios = session.available_scenarios()
        scenario_options = [
            {
                'label': SCENARIO_DISPLAY_NAMES.get(scenario, scenario),
                'value': scenario
            }
            for scenario in available_scenarios
        ]

        # デフォルトで最初のシナリオを選択
        default_scenario = available_scenarios[0] if available_scenarios else None

        # Create navigation links for tabs (Phase 1 Task 1.1: 日本語+絵文字表示)
        # Phase 3-3: Accessibility improvements - navigation with ARIA
        nav_links = html.Div([
            html.Button(
                TAB_DISPLAY_NAMES[tab_key][0],  # 日本語+絵文字表示名
                id={'type': 'tab-btn', 'index': tab_key},  # 内部値（ルーティングキー）
                className="nav-link",
                n_clicks=0,
                style={'margin': '5px', 'padding': '10px', 'cursor': 'pointer'},
                **{
                    'aria-label': TAB_DISPLAY_NAMES[tab_key][1],  # 日本語ARIA-label
                    'tabIndex': 0,
                    'data-testid': f'tab-{tab_key}'  # テスト用ID（言語非依存）
                }
            )
            for tab_key in TAB_KEYS
        ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '5px'}, role="navigation", **{'aria-label': 'タブナビゲーション'})

        return session_id, metadata, scenario_options, default_scenario, nav_links, "Upload successful"

    except Exception as e:
        return None, None, [], None, html.Div(f"Error: {str(e)}"), f"Upload failed: {str(e)}"

# Tab selection callback
@app.callback(
    Output('selected-tab', 'data'),
    [Input({'type': 'tab-btn', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State({'type': 'tab-btn', 'index': dash.dependencies.ALL}, 'id')]
)
def update_selected_tab(n_clicks_list, button_ids):
    if not n_clicks_list or all(n == 0 for n in n_clicks_list):
        return 'overview'

    # Find which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return 'overview'

    triggered_id = ctx.triggered[0]['prop_id']
    if 'tab-btn' in triggered_id:
        import json
        # Extract the index from the triggered button's ID
        # triggered_id format: {"index":"heatmap","type":"tab-btn"}.n_clicks
        try:
            # Parse the JSON portion of the triggered_id
            json_str = triggered_id.split('.')[0]
            button_id = json.loads(json_str)
            return button_id['index']
        except (json.JSONDecodeError, KeyError, IndexError):
            # Fallback: return the first clicked button
            for i, clicks in enumerate(n_clicks_list):
                if clicks and clicks > 0:
                    return button_ids[i]['index']

    return 'overview'

# Phase 3-5: Color scheme update callback
@app.callback(
    Output('selected-color-scheme', 'data'),
    [Input('color-scheme-dropdown', 'value')]
)
def update_color_scheme(color_scheme):
    return color_scheme

# Note: シナリオ選択は render_tab_content で処理される
# scenario-dropdown の値は State として読み取られ、metadata['scenario'] を上書きする

# Tab rendering callback - シナリオ選択を反映（旧システム完全復旧のため）
@app.callback(
    Output('tab-content', 'children'),
    [Input('selected-tab', 'data'),
     Input('session-id', 'data'),
     Input('session-metadata', 'data'),
     Input('selected-color-scheme', 'data'),
     Input('scenario-dropdown', 'value')]  # シナリオ選択を追加
)
def render_tab_content(selected_tab, session_id, metadata, color_scheme, selected_scenario):
    if not session_id:
        return html.Div("Please upload a ZIP file to begin.")

    session = dash_app.get_session(session_id)
    if not session:
        return html.Div("Session not found.")

    # Phase 3-5: Add color scheme to metadata
    if metadata is None:
        metadata = {}
    metadata = dict(metadata)  # Create a copy to avoid modifying the original
    metadata['color_scheme'] = color_scheme or 'modern_blue'

    # シナリオ選択を metadata に反映（旧システム完全復旧のため）
    print(f"DEBUG [render_tab_content]: selected_tab={selected_tab}, selected_scenario={selected_scenario}, metadata_scenario_before={metadata.get('scenario')}")
    if selected_scenario:
        metadata['scenario'] = selected_scenario
        print(f"DEBUG [render_tab_content]: Updated metadata['scenario'] to: {selected_scenario}")
    else:
        print(f"DEBUG [render_tab_content]: WARNING - selected_scenario is None, using metadata default: {metadata.get('scenario')}")

    # Route to specific tab implementations
    if selected_tab == 'overview':
        return dash_app.page_overview(session, metadata)
    elif selected_tab == 'heatmap':
        return dash_app.page_heatmap(session, metadata)
    elif selected_tab == 'shortage':
        return dash_app.page_shortage(session, metadata)
    elif selected_tab == 'individual':
        return dash_app.page_individual(session, metadata)
    elif selected_tab == 'team':
        return dash_app.page_team(session, metadata)
    elif selected_tab == 'fatigue':
        return dash_app.page_fatigue(session, metadata)
    elif selected_tab == 'leave':
        return dash_app.page_leave(session, metadata)
    elif selected_tab == 'fairness':
        return dash_app.page_fairness(session, metadata)
    # Phase 3.1: 品質問題により一時無効化
    # elif selected_tab == 'logic':
    #     return dash_app.page_logic(session, metadata)
    # elif selected_tab == 'ai-analysis':
    #     return dash_app.page_mind_reader(session, metadata)
    elif selected_tab == 'gap-analysis':
        return dash_app.page_gap_analysis(session, metadata)
    elif selected_tab == 'blueprint':
        return dash_app.page_blueprint(session, metadata)
    elif selected_tab == 'optimization':
        return dash_app.page_optimization(session, metadata)
    # Phase 3.1: 品質問題により一時無効化
    # elif selected_tab == 'forecast':
    #     return dash_app.page_forecast(session, metadata)
    elif selected_tab == 'hire-plan':
        return dash_app.page_hire_plan(session, metadata)
    elif selected_tab == 'cost':
        return dash_app.page_cost(session, metadata)
    # Phase 3.1: 品質問題により一時無効化
    # elif selected_tab == 'summary':
    #     return dash_app.page_summary(session, metadata)
    # elif selected_tab == 'reports':
    #     return dash_app.page_reports(session, metadata)
    else:
        # Default fallback for unimplemented tabs
        return html.Div([
            html.H3(f"{selected_tab.replace('-', ' ').title()} Tab"),
            html.P(f"このタブ ({selected_tab}) の実装は進行中です。"),
            html.P(f"Session ID: {session_id}"),
            html.P(f"Scenarios: {', '.join(session.available_scenarios())}"),
        ])

# Test API endpoint for E2E tests
@app.server.route('/__tests__/upload', methods=['POST'])
def test_upload_api():
    """API endpoint for E2E testing"""
    from flask import request, jsonify

    try:
        data = request.get_json()
        contents = data.get('contents')
        session_id = data.get('session_id')

        if not contents or not session_id:
            return jsonify({"error": "Missing required fields"}), 400

        # Process upload
        session = dash_app.load_session_data_from_zip(contents, "test.zip")
        dash_app.register_session(session_id, session)
        metadata = session.metadata()

        return jsonify({
            "progress": {
                "status": "ready",
                "metadata": metadata
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Initialize memory management and session cleanup (Phase 1)
    print("[Phase 1] メモリ管理機構を初期化しています...")
    dash_app.initialize_memory_manager()

    print("[Phase 1] バックグラウンドセッションクリーンアップを開始しています...")
    dash_app.start_session_cleanup()

    print("[Phase 1] 初期化完了。")

    # Initialize visualization engine (Phase 2-2/2-3)
    print("[Phase 2] 可視化エンジンを初期化しています...")
    dash_app.initialize_visualization_engine()

    # Phase 2: Register interactive callbacks
    # Deploy 20.11.2: 明示的にcallbackを登録（ローカルE2E環境用）
    print("[Phase 2] インタラクティブcallbackを登録しています...")
    dash_app.register_interactive_callbacks(app)

    # Register shortage analysis callbacks to our independent app instance
    print("[Phase 2] 不足分析callbackを登録しています...")
    dash_app.register_shortage_callbacks(app)

    # Register insights callbacks (24 callbacks)
    print("[Phase 2] Insights callbackを登録しています...")
    # Phase 2+: Legacy insights callbacks are registered via factory functions
    # inside dash_app.register_interactive_callbacks(). Calling the legacy
    # registrar here caused duplicate Output registration, so we skip it.
    # dash_app.register_insights_callbacks(app)

    # Register blueprint callbacks (3 callbacks)
    # Phase 3.1: Legacy callbacks disabled after Phase 2+
    # print("[Phase 2] Blueprint callbackを登録しています...")
    # dash_app.register_blueprint_callbacks(app)

    # Register heatmap comparison callbacks (1 callback)
    # Phase 3.1: Legacy callbacks disabled after Phase 2+
    # print("[Phase 2] Heatmap比較callbackを登録しています...")
    # dash_app.register_heatmap_comparison_callbacks(app)

    # Register optimization filter callbacks (2 callbacks)
    # Phase 3.1: Legacy callbacks disabled after Phase 2+
    # print("[Phase 2] 最適化フィルターcallbackを登録しています...")
    # dash_app.register_optimization_filter_callbacks(app)

    print("[Phase 2] 初期化完了。アプリケーションを起動します。")

    # Run the dash app on port 8055 for E2E tests
    app.run(
        debug=False,
        host='127.0.0.1',
        port=8055
    )
