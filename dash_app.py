"""Simplified Dash support module used by the test suite.

This re-implementation focuses on the pieces that are exercised by the
unit / integration tests that ship with the repository.  It does not try
to recreate the entire historical Dash application, but it provides the
same public surface (classes/functions) that the tests import while
keeping behaviour compatible with their assertions.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict
import types

import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html

ROOT_DIR = Path(__file__).resolve().parent
LEGACY_DIR = ROOT_DIR / "shift-suite-main(旧システムパッケージ)"
if LEGACY_DIR.exists():
    sys.path.append(str(LEGACY_DIR.resolve()))

try:
    from shift_suite.tasks.blueprint_analyzer import create_blueprint_list
except ModuleNotFoundError:  # pragma: no cover - fallback to legacy package
    import importlib.util

    legacy_package_path = LEGACY_DIR / "shift_suite"
    legacy_blueprint = legacy_package_path / "tasks" / "blueprint_analyzer.py"
    if not legacy_blueprint.exists():
        raise

    legacy_pkg_name = "legacy_shift_suite"
    if legacy_pkg_name not in sys.modules:
        pkg_spec = importlib.util.spec_from_file_location(
            legacy_pkg_name,
            legacy_package_path / "__init__.py",
            submodule_search_locations=[str(legacy_package_path)],
        )
        legacy_pkg = importlib.util.module_from_spec(pkg_spec)
        assert pkg_spec.loader is not None
        pkg_spec.loader.exec_module(legacy_pkg)
        legacy_pkg.__path__ = [str(legacy_package_path)]
        sys.modules[legacy_pkg_name] = legacy_pkg

    source = legacy_blueprint.read_text(encoding="utf-8")
    source = source.replace("shift_suite.tasks", f"{legacy_pkg_name}.tasks")

    module_name = f"{legacy_pkg_name}.blueprint_analyzer"
    legacy_module = types.ModuleType(module_name)
    legacy_module.__file__ = str(legacy_blueprint)
    legacy_module.__package__ = f"{legacy_pkg_name}.tasks"
    exec(compile(source, str(legacy_blueprint), "exec"), legacy_module.__dict__)
    sys.modules[module_name] = legacy_module
    create_blueprint_list = legacy_module.create_blueprint_list  # type: ignore[attr-defined]


log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Phase 3-2: Performance Monitoring Utilities
# -----------------------------------------------------------------------------

def log_performance(operation: str, duration: float, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log performance metrics for operations (Phase 3-2).

    Args:
        operation: Name of the operation
        duration: Duration in seconds
        details: Optional additional details
    """
    level = logging.INFO
    emoji = "✅"

    if duration > PERFORMANCE_THRESHOLD_CRITICAL:
        level = logging.ERROR
        emoji = "🔴"
    elif duration > PERFORMANCE_THRESHOLD_WARNING:
        level = logging.WARNING
        emoji = "⚠️"

    detail_str = ""
    if details:
        detail_str = " | " + ", ".join(f"{k}={v}" for k, v in details.items())

    log.log(
        level,
        f"[パフォーマンス] {emoji} {operation}: {duration:.2f}秒{detail_str}"
    )


def get_memory_usage() -> Dict[str, float]:
    """
    Get current memory usage metrics (Phase 3-2).

    Returns:
        Dictionary with memory usage information
    """
    if _memory_manager is not None:
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            return {
                "rss_mb": mem_info.rss / (1024 * 1024),
                "percent": process.memory_percent()
            }
        except ImportError:
            pass

    # Fallback without psutil
    return {"rss_mb": 0, "percent": 0}


TITLE_ALL = "全体"
RATIO_PLACEHOLDER = "利用できます"

# -----------------------------------------------------------------------------
# Phase 3-1: Data Validation and Error Handling
# -----------------------------------------------------------------------------

# ZIP file size limit (100MB)
MAX_ZIP_SIZE_BYTES = 100 * 1024 * 1024
# Maximum number of files in ZIP (Zip Bomb protection)
MAX_ZIP_FILES = 10000
# Maximum total uncompressed size (Zip Bomb protection)
MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024

# -----------------------------------------------------------------------------
# Phase 3-2: Performance Monitoring
# -----------------------------------------------------------------------------

# Performance thresholds (seconds)
PERFORMANCE_THRESHOLD_WARNING = 2.0  # Warn if operation takes > 2 seconds
PERFORMANCE_THRESHOLD_CRITICAL = 5.0  # Critical if operation takes > 5 seconds

# -----------------------------------------------------------------------------
# Phase 2-1/3-5: Color Schemes for Heatmaps
# -----------------------------------------------------------------------------
# 単色ブルーグラデーション - 濃さで人数を直感的に表現（Phase 2-1）
PROFESSIONAL_BLUE_SCALE = [
    [0, '#f8f9ff'],      # 最薄 - 0人用の非常に薄いブルー
    [0.1, '#e3f2fd'],    # 薄いブルー - 少数
    [0.2, '#bbdefb'],    # やや薄いブルー
    [0.3, '#90caf9'],    # 中薄ブルー
    [0.4, '#64b5f6'],    # 中間ブルー
    [0.5, '#42a5f5'],    # やや濃いブルー
    [0.6, '#2196f3'],    # 中濃ブルー
    [0.7, '#1e88e5'],    # 濃いブルー
    [0.8, '#1976d2'],    # より濃いブルー
    [0.9, '#1565c0'],    # かなり濃いブルー
    [1.0, '#0d47a1']     # 最濃ネイビー - 最大人数
]

# Phase 3-5: プロフェッショナルグレーグラデーション - 落ち着いたモノトーン
PROFESSIONAL_GRAY_SCALE = [
    [0, '#ffffff'],      # 最薄 - 0人用の白
    [0.1, '#f5f5f5'],    # 非常に薄いグレー
    [0.2, '#eeeeee'],    # 薄いグレー
    [0.3, '#e0e0e0'],    # やや薄いグレー
    [0.4, '#bdbdbd'],    # 中薄グレー
    [0.5, '#9e9e9e'],    # 中間グレー
    [0.6, '#757575'],    # 中濃グレー
    [0.7, '#616161'],    # 濃いグレー
    [0.8, '#424242'],    # より濃いグレー
    [0.9, '#212121'],    # かなり濃いグレー
    [1.0, '#000000']     # 最濃黒 - 最大人数
]

# Phase 3-5: バイブラントパープルグラデーション - 鮮やかで目を引く
VIBRANT_PURPLE_SCALE = [
    [0, '#f3e5f5'],      # 最薄 - 0人用の非常に薄いパープル
    [0.1, '#e1bee7'],    # 薄いパープル
    [0.2, '#ce93d8'],    # やや薄いパープル
    [0.3, '#ba68c8'],    # 中薄パープル
    [0.4, '#ab47bc'],    # 中間パープル
    [0.5, '#9c27b0'],    # やや濃いパープル
    [0.6, '#8e24aa'],    # 中濃パープル
    [0.7, '#7b1fa2'],    # 濃いパープル
    [0.8, '#6a1b9a'],    # より濃いパープル
    [0.9, '#4a148c'],    # かなり濃いパープル
    [1.0, '#311b92']     # 最濃ディープパープル - 最大人数
]

# Phase 3-5: カラースキーム辞書 - ユーザー選択用
COLOR_SCHEMES = {
    'modern_blue': {
        'name': 'モダンブルー',
        'scale': PROFESSIONAL_BLUE_SCALE,
        'description': '落ち着いたブルーグラデーション（デフォルト）'
    },
    'professional': {
        'name': 'プロフェッショナル',
        'scale': PROFESSIONAL_GRAY_SCALE,
        'description': 'モノトーングレーグラデーション'
    },
    'vibrant': {
        'name': 'バイブラント',
        'scale': VIBRANT_PURPLE_SCALE,
        'description': '鮮やかなパープルグラデーション'
    }
}

# デフォルトカラースキーム
DEFAULT_COLOR_SCHEME = 'modern_blue'

# -----------------------------------------------------------------------------
# Memory Management Integration (Phase 1)
# -----------------------------------------------------------------------------

try:
    from shift_suite.dash_legacy.components.memory_manager import (
        IntelligentMemoryManager,
        SmartCacheManager,
    )
    MEMORY_MANAGER_AVAILABLE = True
except ImportError:
    log.warning("[メモリ管理] dash_legacy.memory_manager が見つかりません。メモリ管理機能は無効です。")
    MEMORY_MANAGER_AVAILABLE = False
    IntelligentMemoryManager = None
    SmartCacheManager = None

# -----------------------------------------------------------------------------
# Responsive Visualization Engine Integration (Phase 2-2/2-3)
# -----------------------------------------------------------------------------

try:
    from shift_suite.dash_legacy.components.visualization_engine import (
        ResponsiveVisualizationEngine,
        VisualizationConfig,
        create_progress_display,
    )
    VISUALIZATION_ENGINE_AVAILABLE = True
except ImportError:
    log.warning("[可視化エンジン] dash_legacy.visualization_engine が見つかりません。進捗表示機能は無効です。")
    VISUALIZATION_ENGINE_AVAILABLE = False
    ResponsiveVisualizationEngine = None
    VisualizationConfig = None
    create_progress_display = None

# Global memory manager instance (initialized on demand)
_memory_manager: Optional[IntelligentMemoryManager] = None
_memory_manager_lock = threading.RLock()

# Global visualization engine instance (Phase 2-2/2-3)
_visualization_engine: Optional[ResponsiveVisualizationEngine] = None
_visualization_engine_lock = threading.RLock()


# -----------------------------------------------------------------------------
# Data containers
# -----------------------------------------------------------------------------


@dataclass
class HeatmapSettings:
    """Display settings for the overview heatmap."""

    zmax_default: float = 10.0
    quantiles: Dict[str, float] = field(
        default_factory=lambda: {"p90": 10.0, "p95": 10.0, "p99": 10.0}
    )


@dataclass
class ScenarioData:
    """Container for per-scenario artifacts used by the dashboard."""

    name: str
    root_path: Path = Path(".")
    pre_aggregated: pd.DataFrame = field(default_factory=pd.DataFrame)
    heat_staff: pd.DataFrame = field(default_factory=pd.DataFrame)
    heat_ratio: pd.DataFrame = field(default_factory=pd.DataFrame)
    shortage_time: pd.DataFrame = field(default_factory=pd.DataFrame)
    shortage_ratio: pd.DataFrame = field(default_factory=pd.DataFrame)
    heat_settings: HeatmapSettings = field(default_factory=HeatmapSettings)
    roles: List[str] = field(default_factory=list)
    employments: List[str] = field(default_factory=list)
    shortage_role_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    shortage_employment_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_artifacts: List[str] = field(default_factory=list)
    dataset_paths: Dict[str, Path] = field(default_factory=dict)
    data_cache: Dict[str, Any] = field(default_factory=dict)
    analysis_missing: List[str] = field(default_factory=list)
    # Phase 1-3: LRU Cache Management
    cache_access_counts: Dict[str, int] = field(default_factory=dict)
    MAX_CACHE_SIZE: int = 50  # Maximum number of cached datasets

    def metadata(self) -> Dict[str, object]:
        """Return the metadata that tests expect."""
        return {
            "name": self.name,
            "available_roles": self.roles,
            "available_employments": self.employments,
            "has_shortage_role_summary": not self.shortage_role_summary.empty,
            "has_shortage_employment_summary": not self.shortage_employment_summary.empty,
            "shortage_ratio_dates": [str(col) for col in self.shortage_ratio.columns],
            "missing_datasets": sorted(set(self.analysis_missing)),
        }

    def get_dataset(self, key: str, default: Any = None) -> Any:
        """Return a lazily loaded dataset for this scenario with LRU cache management."""
        # Phase 1-3: LRU Cache - Track access on cache hit
        if key in self.data_cache:
            self.cache_access_counts[key] = self.cache_access_counts.get(key, 0) + 1
            return self.data_cache[key]

        spec = SCENARIO_DATASET_SPECS.get(key)
        if spec is None:
            return default

        value, used_path = _load_dataset_from_spec(self.root_path, spec)
        if value is None:
            # Keep track of missing datasets so callers and metadata can surface warnings.
            if key not in self.analysis_missing:
                self.analysis_missing.append(key)
            self.data_cache[key] = default
            return default

        # Phase 1-3: LRU Cache - Evict least used item if cache is full
        if len(self.data_cache) >= self.MAX_CACHE_SIZE:
            self._evict_least_used()

        if used_path is not None:
            self.dataset_paths[key] = used_path
            if key in self.analysis_missing:
                self.analysis_missing = [k for k in self.analysis_missing if k != key]

        self.data_cache[key] = value
        self.cache_access_counts[key] = 1  # Initialize access count
        return value

    def _evict_least_used(self) -> None:
        """Phase 1-3: Evict the least frequently used dataset from cache."""
        if not self.cache_access_counts:
            # Fallback: remove first item if no access counts tracked
            if self.data_cache:
                first_key = next(iter(self.data_cache))
                self.data_cache.pop(first_key, None)
                self.dataset_paths.pop(first_key, None)
                log.debug(f"[LRUキャッシュ] {self.name}: {first_key} を削除（フォールバック）")
            return

        # Find the key with minimum access count
        min_key = min(self.cache_access_counts.keys(),
                     key=lambda k: self.cache_access_counts.get(k, 0))

        # Remove from cache and counts
        self.data_cache.pop(min_key, None)
        self.cache_access_counts.pop(min_key, None)
        self.dataset_paths.pop(min_key, None)

        log.debug(f"[LRUキャッシュ] {self.name}: {min_key} を削除（アクセス数: {self.cache_access_counts.get(min_key, 0)}）")


@dataclass
class SessionData:
    """Container stored per browser session."""

    scenarios: "OrderedDict[str, ScenarioData]"
    source_filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    workspace_root: Optional[Path] = None
    temp_dir: Optional[tempfile.TemporaryDirectory] = field(default=None, repr=False)
    missing_artifacts: Dict[str, List[str]] = field(default_factory=dict)

    def available_scenarios(self) -> List[str]:
        return list(self.scenarios.keys())

    def get_scenario_data(self, scenario_name: Optional[str]) -> Tuple[str, ScenarioData]:
        if scenario_name and scenario_name in self.scenarios:
            return scenario_name, self.scenarios[scenario_name]
        default = next(iter(self.scenarios))
        return default, self.scenarios[default]

    def metadata(self, scenario_name: Optional[str] = None) -> Dict[str, object]:
        scenario_key, scenario = self.get_scenario_data(scenario_name)
        meta = scenario.metadata()
        meta.update(
            {
                "status": "ready",
                "token": str(uuid.uuid4()),
                "filename": self.source_filename,
                "timestamp": self.created_at,
                "scenario": scenario_key,
                "scenarios": self.available_scenarios(),
                "missing_artifacts": self.missing_artifacts.get(scenario_key, []),
            }
        )
        return meta

    def dispose(self) -> None:
        if self.temp_dir is not None:
            try:
                self.temp_dir.cleanup()
            finally:
                self.temp_dir = None


# -----------------------------------------------------------------------------
# Artifact helpers
# -----------------------------------------------------------------------------

SCENARIO_ARTIFACT_EXPECTATIONS: Dict[str, List[str]] = {
    "heatmap": ["heat_ALL.parquet", "heat_ALL.csv", "heat_ALL.xlsx"],
    "heat_ratio": ["heat_ratio.parquet", "heat_ratio.csv"],
    "shortage_time": ["shortage_time.parquet", "shortage_time.csv"],
    "shortage_ratio": ["shortage_ratio.parquet", "shortage_ratio.csv"],
    "mind_reader": ["creator_mind_analysis.json"],
    "fairness": ["fairness_before.parquet", "fairness_before.xlsx"],
}


def _collect_missing_artifacts(
    scenarios: "OrderedDict[str, ScenarioData]"
) -> Dict[str, List[str]]:
    missing: Dict[str, List[str]] = {}
    for scenario_key, scenario in scenarios.items():
        scenario_missing: List[str] = []
        for label, candidates in SCENARIO_ARTIFACT_EXPECTATIONS.items():
            if not any((scenario.root_path / candidate).exists() for candidate in candidates):
                scenario_missing.append(label)
        if scenario_missing:
            missing[scenario_key] = scenario_missing
    return missing


def _ensure_artifacts_from_root(scenario_root: Path, workspace_root: Path) -> None:
    """Copy fallback files from the workspace root into the scenario directory."""
    if not workspace_root.exists():
        return
    for candidates in SCENARIO_ARTIFACT_EXPECTATIONS.values():
        to_path = scenario_root / candidates[0]
        if to_path.exists():
            continue
        for candidate in candidates:
            from_path = workspace_root / candidate
            if from_path.exists():
                to_path.write_bytes(from_path.read_bytes())
                break


def _load_table(
    path: Path, candidates: List[str], index_col: Optional[int | str] = None, **kwargs
) -> pd.DataFrame:
    for candidate in candidates:
        file_path = path / candidate
        if not file_path.exists():
            continue
        try:
            df: pd.DataFrame
            if file_path.suffix == ".parquet":
                df = pd.read_parquet(file_path, **kwargs)
                if index_col is not None:
                    if isinstance(index_col, int):
                        columns = df.columns.tolist()
                        if 0 <= index_col < len(columns):
                            df = df.set_index(columns[index_col])
                    elif index_col in df.columns:
                        df = df.set_index(index_col)
            elif file_path.suffix in {".csv", ".txt"}:
                df = pd.read_csv(file_path, index_col=index_col, **kwargs)
            elif file_path.suffix in {".xlsx", ".xls"}:
                df = pd.read_excel(file_path, index_col=index_col, **kwargs)
            else:
                continue
            return df
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Failed to load %s: %s", file_path, exc, exc_info=True)
    return pd.DataFrame()


# -----------------------------------------------------------------------------
# Dataset helpers for advanced analysis features
# -----------------------------------------------------------------------------

SCENARIO_DATASET_SPECS: Dict[str, Dict[str, Any]] = {
    "long_df": {"filenames": ["intermediate_data.parquet"], "type": "table"},
    "daily_cost": {
        "filenames": ["daily_cost.parquet", "daily_cost.xlsx", "daily_cost.csv"],
        "type": "table",
    },
    "leave_analysis": {"filenames": ["leave_analysis.csv", "leave_analysis.parquet"], "type": "table"},
    "leave_ratio_breakdown": {
        "filenames": ["leave_ratio_breakdown.csv", "leave_ratio_breakdown.parquet"],
        "type": "table",
    },
    "staff_balance_daily": {"filenames": ["staff_balance_daily.csv"], "type": "table"},
    "fairness_before": {
        "filenames": ["fairness_before.parquet", "fairness_before.xlsx"],
        "type": "table",
    },
    "fairness_after": {
        "filenames": ["fairness_after.parquet", "fairness_after.xlsx"],
        "type": "table",
    },
    "fatigue_score": {"filenames": ["fatigue_score.parquet", "fatigue_score.xlsx"], "type": "table"},
    "stats_alerts": {"filenames": ["stats_alerts.parquet", "stats_alerts.csv"], "type": "table"},
    "stats_daily_metrics_raw": {"filenames": ["stats_daily_metrics_raw.parquet"], "type": "table"},
    "stats_monthly_summary": {"filenames": ["stats_monthly_summary.parquet"], "type": "table"},
    "stats_overall_summary": {"filenames": ["stats_overall_summary.parquet"], "type": "table"},
    "cost_benefit": {
        "filenames": ["cost_benefit.parquet", "cost_benefit.xlsx", "cost_benefit.csv"],
        "type": "table",
    },
    "hire_plan": {"filenames": ["hire_plan.parquet", "hire_plan.xlsx", "hire_plan.csv"], "type": "table"},
    "hire_plan_meta": {"filenames": ["hire_plan_meta.parquet", "hire_plan_meta.csv"], "type": "table"},
    "optimization_score_time": {"filenames": ["optimization_score_time.parquet"], "type": "table"},
    "forecast": {"filenames": ["forecast.parquet"], "type": "table"},
    "forecast_json": {"filenames": ["forecast.json"], "type": "json"},
    "forecast_history": {"filenames": ["forecast_history.csv"], "type": "table"},
    "demand_series": {"filenames": ["demand_series.csv"], "type": "table"},
    "creator_mind_analysis": {"filenames": ["creator_mind_analysis.json"], "type": "json"},
    "rest_time": {"filenames": ["rest_time.csv"], "type": "table"},
    "rest_time_monthly": {"filenames": ["rest_time_monthly.csv"], "type": "table"},
    "shortage_weekday_timeslot_summary": {
        "filenames": [
            "shortage_weekday_timeslot_summary.parquet",
            "shortage_weekday_timeslot_summary.csv",
            "shortage_weekday_timeslot_summary.xlsx",
        ],
        "type": "table",
    },
    "blueprint_analysis": {"filenames": ["blueprint_analysis.json"], "type": "json"},
    "creation_logic_analysis": {
        "filenames": [
            "creation_logic_analysis.json",
            "creation_logic_analysis.parquet",
            "creation_logic_analysis.csv",
        ],
        "type": "json",
    },
    "mind_reader_analysis": {
        "filenames": [
            "mind_reader_analysis.json",
            "mind_reader_analysis.parquet",
            "mind_reader_analysis.csv",
        ],
        "type": "json",
    },
    "gap_summary": {"filenames": ["gap_summary.parquet", "gap_summary.xlsx"], "type": "table"},
    "gap_heatmap": {"filenames": ["gap_heatmap.parquet", "gap_heatmap.xlsx"], "type": "table"},
    "advanced_analysis_report": {
        "filenames": [
            "ai_comprehensive_report.json",
            "ai_comprehensive_report_20250908_151347_36f573f7.json",
        ],
        "type": "json",
        "allow_empty": True,
    },
}


def _load_dataset_from_spec(root: Path, spec: Dict[str, Any]) -> Tuple[Any, Optional[Path]]:
    """Return a dataset according to the provided specification."""
    candidates = spec.get("filenames", [])
    dataset_type = spec.get("type", "table")
    index_col = spec.get("index_col")

    for name in candidates:
        candidate_path = root / name
        if not candidate_path.exists():
            continue
        try:
            if dataset_type == "table":
                df = _load_table(root, [name], index_col=index_col)
                allow_empty = spec.get("allow_empty", False)
                if not df.empty or allow_empty:
                    return df, candidate_path
            elif dataset_type == "json":
                with candidate_path.open("r", encoding="utf-8") as handle:
                    return json.load(handle), candidate_path
            elif dataset_type == "text":
                return candidate_path.read_text(encoding="utf-8"), candidate_path
            elif dataset_type == "binary":
                return candidate_path.read_bytes(), candidate_path
        except Exception:  # pragma: no cover - defensive
            log.warning("Failed to load dataset %s from %s", dataset_type, candidate_path, exc_info=True)
            continue
    return None, None


def _initialize_dataset_inventory(scenario: ScenarioData) -> None:
    """Populate dataset availability metadata for the given scenario."""
    seen_missing: set[str] = set(scenario.analysis_missing)
    for key, spec in SCENARIO_DATASET_SPECS.items():
        if key in scenario.dataset_paths:
            continue

        candidates = spec.get("filenames", [])
        found_path: Optional[Path] = None
        for name in candidates:
            candidate = scenario.root_path / name
            if candidate.exists():
                found_path = candidate
                break

        if found_path is not None:
            scenario.dataset_paths[key] = found_path
        else:
            if key not in seen_missing:
                scenario.analysis_missing.append(key)
                seen_missing.add(key)


def _ensure_dataframe(value: Any) -> pd.DataFrame:
    """Convert the provided value to a pandas DataFrame when possible."""
    if isinstance(value, pd.DataFrame):
        return value
    if value is None:
        return pd.DataFrame()
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        try:
            return pd.DataFrame(value)
        except ValueError:
            try:
                return pd.DataFrame.from_dict(value, orient="index")
            except ValueError:
                return pd.DataFrame()
    return pd.DataFrame()


def _format_cell(value: Any) -> str:
    """Convert a dataframe cell value to a short string for display."""
    if isinstance(value, (float, int)):
        return f"{value:.3g}"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            return str(value)
    if value is None:
        return ""
    return str(value)


def _render_dataframe(df: pd.DataFrame, max_rows: int = 10) -> html.Table:
    """Render a pandas DataFrame as a Dash HTML table."""
    if df is None or df.empty:
        return html.Table([html.Tr([html.Td("データがありません。")])], className="table table-sm")

    limited = df.head(max_rows)
    header_cells = [html.Th(str(col)) for col in limited.columns]
    header = html.Thead(html.Tr(header_cells))

    body_rows = []
    for _, row in limited.iterrows():
        body_rows.append(html.Tr([html.Td(_format_cell(value)) for value in row]))
    body = html.Tbody(body_rows)

    return html.Table([header, body], className="table table-sm table-striped table-bordered")


# -----------------------------------------------------------------------------
# Session registry
# -----------------------------------------------------------------------------

SESSION_REGISTRY: "OrderedDict[str, SessionData]" = OrderedDict()
SESSION_LOCK = threading.RLock()

# Session management configuration
SESSION_TIMEOUT = 3600  # 1 hour (seconds)
MAX_SESSIONS = 100  # Maximum number of concurrent sessions


def initialize_memory_manager() -> None:
    """Initialize the global memory manager (idempotent)."""
    global _memory_manager

    if not MEMORY_MANAGER_AVAILABLE:
        log.warning("[メモリ管理] メモリマネージャーが利用できません。")
        return

    with _memory_manager_lock:
        if _memory_manager is None:
            _memory_manager = IntelligentMemoryManager(
                max_memory_percent=70.0,
                cleanup_threshold_percent=80.0,
                emergency_threshold_percent=90.0,
                monitoring_interval=30
            )
            _memory_manager.start_monitoring()
            log.info("[メモリ管理] IntelligentMemoryManager を初期化しました。")


def get_memory_manager() -> Optional[IntelligentMemoryManager]:
    """Get the global memory manager instance."""
    return _memory_manager


def initialize_visualization_engine() -> None:
    """Initialize the global visualization engine (idempotent) - Phase 2-2/2-3."""
    global _visualization_engine

    if not VISUALIZATION_ENGINE_AVAILABLE:
        log.warning("[可視化エンジン] 可視化エンジンが利用できません。")
        return

    with _visualization_engine_lock:
        if _visualization_engine is None:
            config = VisualizationConfig(
                color_scheme="modern_blue",
                enable_interactivity=True,
                show_progress=True
            )
            _visualization_engine = ResponsiveVisualizationEngine(config)
            log.info("[可視化エンジン] ResponsiveVisualizationEngine を初期化しました。")


def get_visualization_engine() -> Optional[ResponsiveVisualizationEngine]:
    """Get the global visualization engine instance."""
    return _visualization_engine


def create_progress_indicator(step: str, progress: int, remaining: int = 0) -> html.Div:
    """
    Create a progress indicator component (Phase 2-3).

    Args:
        step: Current processing step description
        progress: Progress percentage (0-100)
        remaining: Estimated remaining seconds

    Returns:
        html.Div containing the progress indicator, or empty div if engine unavailable
    """
    if not VISUALIZATION_ENGINE_AVAILABLE or _visualization_engine is None:
        # Fallback: simple text-based progress indicator
        return html.Div([
            html.P(f"🔄 {step} ({progress}%)"),
            html.P(f"⏱️ 残り約{remaining}秒") if remaining > 0 else html.Div()
        ], style={'padding': '10px', 'textAlign': 'center'})

    # Use visualization engine's progress display
    return _visualization_engine.create_progress_visualization(
        current_step=step,
        progress_percentage=progress,
        estimated_remaining=remaining,
        device_type="desktop"  # Server-side rendering defaults to desktop
    )


def register_session(session_id: str, data: SessionData) -> SessionData:
    """Register a new session with memory management integration."""
    with SESSION_LOCK:
        SESSION_REGISTRY[session_id] = data

        # Register with memory manager if available
        if _memory_manager is not None:
            _memory_manager.register_cache_object(f"session_{session_id}", data)
            log.debug(f"[セッション管理] セッション登録: {session_id}")

    return data


def get_session(session_id: Optional[str]) -> Optional[SessionData]:
    """Get a session by ID."""
    if not session_id:
        return None
    with SESSION_LOCK:
        return SESSION_REGISTRY.get(session_id)


def cleanup_expired_sessions() -> int:
    """
    Remove expired sessions based on timeout and maximum session limit.

    Returns:
        Number of sessions cleaned up.
    """
    current_time = time.time()
    cleaned_count = 0

    with SESSION_LOCK:
        # Phase 1: Remove expired sessions (timeout-based)
        expired = [
            sid for sid, session in SESSION_REGISTRY.items()
            if (current_time - session.created_at) > SESSION_TIMEOUT
        ]

        for sid in expired:
            session = SESSION_REGISTRY.pop(sid)
            session.dispose()  # Cleanup temp directories
            cleaned_count += 1
            log.info(f"[セッション管理] 期限切れセッション削除: {sid} (経過時間: {current_time - session.created_at:.0f}秒)")

        # Phase 2: Remove oldest sessions if exceeding maximum limit
        if len(SESSION_REGISTRY) > MAX_SESSIONS:
            oldest_sessions = sorted(
                SESSION_REGISTRY.items(),
                key=lambda x: x[1].created_at
            )[:len(SESSION_REGISTRY) - MAX_SESSIONS]

            for sid, session in oldest_sessions:
                SESSION_REGISTRY.pop(sid)
                session.dispose()
                cleaned_count += 1
                log.info(f"[セッション管理] 容量超過セッション削除: {sid}")

    if cleaned_count > 0:
        log.info(f"[セッション管理] {cleaned_count}個のセッションをクリーンアップしました。")

    return cleaned_count


def _session_cleanup_loop() -> None:
    """Background loop for periodic session cleanup (runs every 5 minutes)."""
    while True:
        try:
            time.sleep(300)  # 5 minutes
            cleanup_expired_sessions()
        except Exception as e:
            log.error(f"[セッション管理] クリーンアップループエラー: {e}", exc_info=True)


def start_session_cleanup() -> None:
    """Start the background session cleanup thread."""
    cleanup_thread = threading.Thread(target=_session_cleanup_loop, daemon=True)
    cleanup_thread.start()
    log.info("[セッション管理] バックグラウンドクリーンアップを開始しました。")


def get_dataset(
    session_id: Optional[str],
    key: str,
    scenario_name: Optional[str] = None,
    default: Any = None,
) -> Any:
    """Helper to retrieve a lazily loaded dataset for a given session."""
    session = get_session(session_id)
    if session is None:
        return default

    _, scenario = session.get_scenario_data(scenario_name)
    return scenario.get_dataset(key, default)


# -----------------------------------------------------------------------------
# Blueprint analysis tab
# -----------------------------------------------------------------------------

def _ensure_required_dataset(scenario: ScenarioData, dataset_key: str) -> Optional[pd.DataFrame]:
    """Load a required dataset and register it as missing when empty."""
    df = scenario.get_dataset(dataset_key)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    if isinstance(df, dict):
        converted = _ensure_dataframe(df)
        if not converted.empty:
            return converted
    return None


def _blueprint_analysis_for_scenario(scenario: ScenarioData) -> Dict[str, Any]:
    """Run or retrieve cached blueprint analysis results for the scenario."""
    cache_key = "__blueprint_analysis"
    cached = scenario.data_cache.get(cache_key)
    if cached is not None:
        return cached

    long_df = scenario.get_dataset("long_df")
    if long_df is None or (isinstance(long_df, pd.DataFrame) and long_df.empty):
        scenario.analysis_missing.append("long_df")
        scenario.data_cache[cache_key] = {}
        return {}

    try:
        blueprint_data = create_blueprint_list(long_df)
    except Exception:  # pragma: no cover - defensive
        log.exception("Failed to execute blueprint analysis for scenario %s", scenario.name)
        blueprint_data = {}

    scenario.data_cache[cache_key] = blueprint_data
    return blueprint_data


def _build_tradeoff_summary(tradeoff_info: Dict[str, Any]) -> html.Div:
    """Render tradeoff summary for the blueprint analysis."""
    if not tradeoff_info:
        return html.Div("トレードオフ分析データがありません。")

    pairs = tradeoff_info.get("strongest_tradeoffs") or []
    items = []
    for pair in pairs[:5]:
        if isinstance(pair, dict):
            label = pair.get("label") or pair.get("name") or "Trade-off"
            corr = pair.get("correlation")
            if corr is not None:
                badge = f"{label} (相関: {corr:.2f})"
            else:
                badge = label
        else:
            badge = str(pair)
        items.append(html.Li(badge))

    if not items:
        items.append(html.Li("主要なトレードオフが見つかりませんでした。"))
    return html.Div(
        [
            html.H5("主要トレードオフ"),
            html.Ul(items),
        ]
    )


# -----------------------------------------------------------------------------
# Phase 3-6: Refactoring Helper Functions
# -----------------------------------------------------------------------------

def create_missing_data_message(
    tab_name: str,
    required_files: List[str],
    additional_info: str = ""
) -> html.Div:
    """データ不足時の統一エラーメッセージを生成 (Phase 3-6).

    Args:
        tab_name: タブ名（例: "個人分析", "疲労度分析"）
        required_files: 必要なファイル名のリスト
        additional_info: 追加の説明情報（オプション）

    Returns:
        html.Div: スタイル付きエラーメッセージ
    """
    return html.Div([
        html.H3(f"{tab_name} - データが不足しています", style={"color": "#d32f2f"}),
        html.P("以下のデータファイルが必要です:"),
        html.Ul([html.Li(file) for file in required_files]),
        html.P(additional_info) if additional_info else None,
    ], style={
        "padding": "20px",
        "backgroundColor": "#fff3cd",
        "borderRadius": "5px",
        "border": "1px solid #ffc107"
    })


def get_heatmap_colorscale(metadata: Optional[dict]) -> List[List]:
    """メタデータからカラースキームを安全に取得 (Phase 3-6).

    Args:
        metadata: メタデータ辞書（color_schemeキーを含む可能性がある）

    Returns:
        List[List]: Plotly用カラースケール [[position, color], ...]
    """
    if metadata is None:
        metadata = {}

    color_scheme = metadata.get('color_scheme', DEFAULT_COLOR_SCHEME)
    scheme_data = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES[DEFAULT_COLOR_SCHEME])
    return scheme_data['scale']


def page_blueprint(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Blueprint analysis page (simplified legacy復旧版)."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    blueprint_data = _blueprint_analysis_for_scenario(scenario)
    if not blueprint_data:
        missing_msg = "必要な分析データが不足しています。"
        if scenario.analysis_missing:
            missing_msg += " 不足: " + ", ".join(sorted(set(scenario.analysis_missing)))
        return html.Div(
            [
                html.H3("ブループリント分析"),
                html.P(missing_msg),
            ]
        )

    rules_df = _ensure_dataframe(blueprint_data.get("rules_df"))
    facts_df = _ensure_dataframe(blueprint_data.get("facts_df"))
    tradeoffs = blueprint_data.get("tradeoffs", {})

    summary_items = []
    if not rules_df.empty:
        summary_items.append(html.Li(f"暗黙ルール数: {len(rules_df)}"))
    if not facts_df.empty:
        summary_items.append(html.Li(f"抽出された事実数: {len(facts_df)}"))
    if tradeoffs:
        scatter = tradeoffs.get("scatter_data") or []
        if scatter:
            summary_items.append(html.Li(f"トレードオフ観測点: {len(scatter)}"))
    if not summary_items:
        summary_items.append(html.Li("分析対象データが少ないため、詳細は表示できません。"))

    content: List[html.Component] = [
        html.H3("ブループリント分析"),
        html.P("旧システムの暗黙知分析タブを復旧したビューです。"),
        html.Ul(summary_items),
    ]

    if not rules_df.empty:
        content.extend(
            [
                html.H4("暗黙ルール（上位表示）"),
                _render_dataframe(rules_df, max_rows=10),
            ]
        )

    if tradeoffs:
        content.append(_build_tradeoff_summary(tradeoffs))

    if not facts_df.empty:
        content.extend(
            [
                html.H4("客観的事実（上位表示）"),
                _render_dataframe(facts_df, max_rows=10),
            ]
        )

    blueprint_json = scenario.get_dataset("blueprint_analysis")
    if blueprint_json:
        preview = json.dumps(blueprint_json, ensure_ascii=False, indent=2)
        content.extend(
            [
                html.H4("ブループリント分析ファイルプレビュー"),
                html.Pre(preview[:2000] + ("..." if len(preview) > 2000 else "")),
            ]
        )

    return html.Div(content, className="blueprint-analysis-tab")


# -----------------------------------------------------------------------------
# Data ingestion
# -----------------------------------------------------------------------------


def _validate_and_decode_contents(contents: str) -> bytes:
    """Validate and decode base64-encoded ZIP contents (Phase 3-1)."""
    if not contents:
        raise ValueError("❌ アップロードされたファイルが空です。ZIPファイルを選択してください。")
    if "," not in contents:
        raise ValueError("❌ 無効なファイル形式です。正しいZIPファイルをアップロードしてください。")

    header, encoded = contents.split(",", 1)
    if "base64" not in header:
        raise ValueError("❌ ファイルのエンコーディングが不正です。ブラウザを更新して再試行してください。")

    try:
        return base64.b64decode(encoded)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("❌ ファイルのデコードに失敗しました。破損している可能性があります。") from exc


def _validate_zip_size(decoded: bytes) -> None:
    """Validate ZIP file size does not exceed limit (Phase 3-1)."""
    zip_size = len(decoded)
    if zip_size > MAX_ZIP_SIZE_BYTES:
        size_mb = zip_size / (1024 * 1024)
        max_mb = MAX_ZIP_SIZE_BYTES / (1024 * 1024)
        raise ValueError(
            f"❌ ファイルサイズが大きすぎます。\n"
            f"アップロードサイズ: {size_mb:.1f}MB\n"
            f"最大サイズ: {max_mb:.0f}MB"
        )


def _extract_zip_with_security_checks(
    decoded: bytes, temp_root: Path, temp_dir: tempfile.TemporaryDirectory, filename: Optional[str]
) -> None:
    """Extract ZIP with Zip Bomb protection (Phase 3-1)."""
    try:
        with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
            # Check number of files (Zip Bomb protection)
            file_count = len(zf.namelist())
            if file_count > MAX_ZIP_FILES:
                temp_dir.cleanup()
                raise ValueError(
                    f"❌ ZIPファイル内のファイル数が多すぎます。\n"
                    f"ファイル数: {file_count}\n"
                    f"最大許容数: {MAX_ZIP_FILES}"
                )

            # Check total uncompressed size (Zip Bomb protection)
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_UNCOMPRESSED_SIZE:
                temp_dir.cleanup()
                size_mb = total_size / (1024 * 1024)
                max_mb = MAX_UNCOMPRESSED_SIZE / (1024 * 1024)
                raise ValueError(
                    f"❌ 解凍後のファイルサイズが大きすぎます。\n"
                    f"解凍後サイズ: {size_mb:.1f}MB\n"
                    f"最大サイズ: {max_mb:.0f}MB"
                )

            # Extract files
            zf.extractall(temp_root)
            log.info(f"[ZIP検証] ファイル数: {file_count}, 解凍サイズ: {total_size / (1024 * 1024):.1f}MB")

    except zipfile.BadZipFile as exc:
        temp_dir.cleanup()
        raise ValueError(
            f"❌ ZIPファイルの解凍に失敗しました。\n"
            f"ファイル '{filename}' が破損しているか、ZIP形式ではありません。"
        ) from exc
    except Exception as exc:
        temp_dir.cleanup()
        raise ValueError(f"❌ ファイル処理中にエラーが発生しました: {str(exc)}") from exc


def _discover_and_validate_scenarios(temp_root: Path, temp_dir: tempfile.TemporaryDirectory) -> List[Path]:
    """Discover and validate scenario directories (Phase 3-1)."""
    scenario_paths = sorted(
        [p for p in temp_root.iterdir() if p.is_dir() and p.name.startswith("out_")]
    )
    if not scenario_paths:
        scenario_paths = [temp_root]

    # Validate scenario directories
    if not scenario_paths or all(not list(p.iterdir()) for p in scenario_paths):
        temp_dir.cleanup()
        raise ValueError(
            "❌ ZIPファイルにシナリオデータが見つかりません。\n"
            "期待されるフォルダ: 'out_' で始まるディレクトリ、または分析結果ファイル\n"
            "アップロードしたファイルが正しい分析結果ZIPか確認してください。"
        )

    return scenario_paths


def _build_scenarios_dict(
    scenario_paths: List[Path], temp_root: Path, temp_dir: tempfile.TemporaryDirectory
) -> Tuple["OrderedDict[str, ScenarioData]", Dict[str, List[str]]]:
    """Build scenarios dictionary with artifact tracking (Phase 3-1)."""
    scenarios: "OrderedDict[str, ScenarioData]" = OrderedDict()
    for path in scenario_paths:
        _ensure_artifacts_from_root(path, temp_root)
        scenario = _build_scenario_data(path)
        scenarios[path.name] = scenario

    # Validate that at least one scenario has critical data
    has_valid_data = any(
        not scenario.heat_staff.empty or not scenario.shortage_time.empty
        for scenario in scenarios.values()
    )
    if not has_valid_data:
        temp_dir.cleanup()
        raise ValueError(
            "❌ 有効な分析データが見つかりません。\n"
            "必須データ: ヒートマップ（heatmap）または不足時間（shortage_time）\n"
            "ZIPファイルに正しい分析結果が含まれているか確認してください。"
        )

    # Collect missing artifacts
    missing = _collect_missing_artifacts(scenarios)
    for key, scenario in scenarios.items():
        combined = list(missing.get(key, []))
        if scenario.analysis_missing:
            combined.extend(sorted(set(scenario.analysis_missing)))
        if combined:
            combined = sorted(set(combined))
        scenario.missing_artifacts = combined
        missing[key] = combined

    return scenarios, missing


def load_session_data_from_zip(contents: str, filename: Optional[str]) -> SessionData:
    """Load and validate session data from ZIP file (Phase 3-1, 3-2)."""
    start_time = time.time()

    # Decode and validate contents
    decoded = _validate_and_decode_contents(contents)
    _validate_zip_size(decoded)

    # Create temporary directory
    temp_dir = tempfile.TemporaryDirectory(prefix="shift_suite_dash_")
    temp_root = Path(temp_dir.name)

    # Extract ZIP with security checks
    _extract_zip_with_security_checks(decoded, temp_root, temp_dir, filename)

    # Discover and validate scenarios
    scenario_paths = _discover_and_validate_scenarios(temp_root, temp_dir)

    # Build scenarios dictionary
    scenarios, missing = _build_scenarios_dict(scenario_paths, temp_root, temp_dir)

    # Create session
    session = SessionData(
        scenarios=scenarios,
        source_filename=filename,
        workspace_root=temp_root,
        temp_dir=temp_dir,
        missing_artifacts=missing,
    )

    # Log performance metrics
    duration = time.time() - start_time
    mem_usage = get_memory_usage()
    log_performance(
        "ZIPファイル読み込み",
        duration,
        {
            "filename": filename or "unknown",
            "scenarios": len(scenarios),
            "memory_mb": f"{mem_usage['rss_mb']:.1f}",
        }
    )

    return session


def _build_scenario_data(path: Path) -> ScenarioData:
    heat_staff = _load_table(path, SCENARIO_ARTIFACT_EXPECTATIONS["heatmap"], index_col=0)
    heat_ratio = _load_table(path, SCENARIO_ARTIFACT_EXPECTATIONS["heat_ratio"], index_col=0)
    shortage_time = _load_table(path, SCENARIO_ARTIFACT_EXPECTATIONS["shortage_time"], index_col=0)
    shortage_ratio = _load_table(path, SCENARIO_ARTIFACT_EXPECTATIONS["shortage_ratio"], index_col=0)

    if not heat_staff.empty:
        index_name = heat_staff.index.name or "time"
        pre_aggregated = (
            heat_staff.reset_index()
            .rename(columns={index_name: "time"})
            .melt(id_vars=["time"], var_name="date_lbl", value_name="staff_count")
        )
    else:
        pre_aggregated = pd.DataFrame()

    shortage_role_summary = _load_table(
        path, ["shortage_role_summary.parquet", "shortage_role_summary.csv"]
    )
    shortage_employment_summary = _load_table(
        path, ["shortage_employment_summary.parquet", "shortage_employment_summary.csv"]
    )

    roles: List[str] = []
    if not shortage_role_summary.empty and "role" in shortage_role_summary.columns:
        roles = sorted(shortage_role_summary["role"].dropna().unique().tolist())
    elif "role" in pre_aggregated.columns:
        roles = sorted(pre_aggregated["role"].dropna().unique().tolist())

    employments: List[str] = []
    if not shortage_employment_summary.empty and "employment" in shortage_employment_summary.columns:
        employments = sorted(shortage_employment_summary["employment"].dropna().unique().tolist())
    elif "employment" in pre_aggregated.columns:
        employments = sorted(pre_aggregated["employment"].dropna().unique().tolist())

    if not roles:
        roles = ["all"]
    if not employments:
        employments = ["all"]

    scenario = ScenarioData(
        name=path.name,
        root_path=path,
        pre_aggregated=pre_aggregated,
        heat_staff=heat_staff,
        heat_ratio=heat_ratio,
        shortage_time=shortage_time,
        shortage_ratio=shortage_ratio,
        roles=roles,
        employments=employments,
        shortage_role_summary=shortage_role_summary,
        shortage_employment_summary=shortage_employment_summary,
    )
    _initialize_dataset_inventory(scenario)
    return scenario


# -----------------------------------------------------------------------------
# Heatmap helpers
# -----------------------------------------------------------------------------

def _empty_figure(message: str = "No data") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(size=16),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def _calculate_total_shortage_hours(shortage_df: pd.DataFrame) -> float:
    """Convert positive shortage slots to hours (0.5h per slot)."""
    if shortage_df.empty:
        return 0.0
    positive = shortage_df.clip(lower=0)
    slots = positive.to_numpy().sum()
    return float(slots) * 0.5


def _build_comparison_heatmap_figure(
    scenario: ScenarioData,
    role: str,
    employment: str,
    mode: str,
    zmode: str,
    slider_value: float,
) -> go.Figure:
    df = scenario.pre_aggregated
    if df.empty:
        return _empty_figure("データがありません")

    filtered = df.copy()
    if role != "all" and "role" in filtered.columns:
        filtered = filtered.loc[filtered["role"] == role]
    if employment != "all" and "employment" in filtered.columns:
        filtered = filtered.loc[filtered["employment"] == employment]

    if filtered.empty:
        return _empty_figure("データがありません")

    if mode == "ratio":
        return _empty_figure(RATIO_PLACEHOLDER)

    pivot = filtered.pivot_table(
        index="time", columns="date_lbl", values="staff_count", aggfunc="mean"
    )
    if pivot.empty:
        return _empty_figure("データがありません")

    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale=PROFESSIONAL_BLUE_SCALE,
        zmin=0,
        zmax=slider_value,
        labels=dict(x="Date", y="Timeslot", color="Staff Count"),
    )

    if role == "all" and employment == "all":
        title = TITLE_ALL
    elif employment == "all":
        title = role
    elif role == "all":
        title = employment
    else:
        title = f"{role} / {employment}"
    fig.update_layout(title=title, margin=dict(l=20, r=20, t=40, b=20), height=360)
    return fig


def update_heatmap(
    mode: str,
    slider_value: Optional[float],
    zmode: str,
    selected_scenario: Optional[str],
    session_id: Optional[str],
) -> Tuple[go.Figure, bool, float]:
    session = get_session(session_id)
    if session is None:
        return _empty_figure("セッションが見つかりません"), True, slider_value or 10.0

    _, scenario = session.get_scenario_data(selected_scenario)
    if mode == "ratio" and not scenario.heat_ratio.empty:
        data = scenario.heat_ratio
        fig = px.imshow(
            data,
            aspect="auto",
            color_continuous_scale=PROFESSIONAL_BLUE_SCALE,
            labels=dict(x="Date", y="Timeslot", color="Ratio"),
        )
        return fig, True, slider_value or scenario.heat_settings.zmax_default

    if scenario.heat_staff.empty:
        return _empty_figure("データがありません"), True, slider_value or scenario.heat_settings.zmax_default

    zmax = slider_value or scenario.heat_settings.zmax_default
    fig = px.imshow(
        scenario.heat_staff,
        aspect="auto",
        color_continuous_scale=PROFESSIONAL_BLUE_SCALE,
        zmin=0,
        zmax=zmax,
        labels=dict(x="Date", y="Timeslot", color="Staff Count"),
    )
    return fig, False, zmax


def update_heatmap_comparison_panel(
    role_value: str,
    employment_value: str,
    mode: str,
    slider_value: Optional[float],
    zmode: str,
    selected_scenario: Optional[str],
    session_id: Optional[str],
) -> go.Figure:
    session = get_session(session_id)
    if session is None:
        return _empty_figure("セッションが見つかりません")
    _, scenario = session.get_scenario_data(selected_scenario)
    return _build_comparison_heatmap_figure(
        scenario, role_value, employment_value, mode, zmode, slider_value or 10.0
    )


# -----------------------------------------------------------------------------
# Logic Analysis page
# -----------------------------------------------------------------------------


def page_logic(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Logic analysis tab showing shift creation decision rules."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Check if we have long_df data
    long_df = scenario.get_dataset("long_df")
    if long_df is None or long_df.empty:
        return create_missing_data_message(
            tab_name="🔍 ロジック解明",
            required_files=["intermediate_data.parquet (long_df)"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )

    # Try to get cached analysis first
    cached_analysis = scenario.get_dataset("creation_logic_analysis")

    if cached_analysis:
        # Display cached results
        return _render_logic_analysis_from_cache(cached_analysis)

    # If no cache, provide option to run analysis
    return html.Div([
        html.H3("🔍 ロジック解明"),
        html.P("シフト作成のロジックを分析します。"),
        html.Hr(),

        html.Div([
            html.H4("分析レベルを選択"),
            html.P("データサイズに応じて適切な分析レベルを選択してください："),
            html.Ul([
                html.Li("高速 (Fast): 約10秒、サンプル500行、決定木深さ2"),
                html.Li("標準 (Standard): 約30秒、サンプル5000行、決定木深さ3"),
                html.Li("詳細 (Detailed): 数分、全データ使用、完全分析"),
            ]),
        ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),

        html.Hr(),

        # Analysis info
        html.Div([
            _create_kpi_card("データ行数", f"{len(long_df):,} 行"),
            _create_kpi_card("職員数", f"{long_df['staff'].nunique() if 'staff' in long_df.columns else 0} 人"),
            _create_kpi_card("分析期間", f"{long_df['ds'].min().date()} ~ {long_df['ds'].max().date()}" if 'ds' in long_df.columns else "N/A"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.Hr(),

        html.P("⚠️ 注意: ロジック解明タブの完全な実装には shift_suite.tasks.quick_logic_analysis モジュールが必要です。",
               style={"color": "#856404", "backgroundColor": "#fff3cd", "padding": "15px", "borderRadius": "5px", "border": "1px solid #ffeaa7"}),

        html.P("現在は creation_logic_analysis.json キャッシュファイルがある場合のみ結果を表示できます。"),
    ])


def _render_logic_analysis_from_cache(analysis_data: dict) -> html.Div:
    """Render logic analysis results from cached JSON data."""
    content = [
        html.H3("🔍 ロジック解明"),
        html.P("シフト作成ロジックの分析結果を表示します。"),
        html.Hr(),
    ]

    # Basic statistics
    if "statistics" in analysis_data:
        stats = analysis_data["statistics"]
        content.extend([
            html.H4("基本統計"),
            html.Div([
                _create_kpi_card("分析行数", f"{stats.get('total_rows', 0):,} 行"),
                _create_kpi_card("ユニーク職員", f"{stats.get('unique_staff', 0)} 人"),
                _create_kpi_card("ユニーク勤務コード", f"{stats.get('unique_codes', 0)} 種類"),
                _create_kpi_card("分析時間", f"{stats.get('analysis_duration', 0):.2f} 秒"),
            ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
            html.Hr(),
        ])

    # Decision rules
    if "rules" in analysis_data:
        rules = analysis_data["rules"]
        if isinstance(rules, list) and len(rules) > 0:
            rules_df = pd.DataFrame(rules[:10])  # Top 10 rules
            content.extend([
                html.H4("抽出されたルール TOP10"),
                _render_dataframe(rules_df, max_rows=10),
                html.Hr(),
            ])

    # Feature importance
    if "feature_importance" in analysis_data:
        importance = analysis_data["feature_importance"]
        if isinstance(importance, dict) and len(importance) > 0:
            importance_df = pd.DataFrame([
                {"特徴量": k, "重要度": v}
                for k, v in sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
            ])

            fig = px.bar(
                importance_df,
                x="重要度",
                y="特徴量",
                orientation="h",
                title="特徴量重要度 TOP10",
                labels={"特徴量": "Feature", "重要度": "Importance"},
                color="重要度",
                color_continuous_scale="Blues",
            )

            content.extend([
                html.H4("特徴量重要度"),
                dcc.Graph(figure=fig),
                html.Hr(),
            ])

    # Decision tree visualization
    if "decision_tree" in analysis_data:
        tree_info = analysis_data["decision_tree"]
        content.extend([
            html.H4("決定木の構造"),
            html.P(f"深さ: {tree_info.get('max_depth', 'N/A')}"),
            html.P(f"ノード数: {tree_info.get('n_nodes', 'N/A')}"),
            html.P(f"葉ノード数: {tree_info.get('n_leaves', 'N/A')}"),
            html.Hr(),
        ])

    # JSON preview
    content.extend([
        html.H4("分析結果JSON（プレビュー）"),
        html.Pre(
            json.dumps(analysis_data, ensure_ascii=False, indent=2)[:2000] + "...",
            style={"backgroundColor": "#f5f5f5", "padding": "15px", "borderRadius": "5px", "fontSize": "12px", "overflow": "auto"}
        ),
    ])

    return html.Div(content)


# -----------------------------------------------------------------------------
# AI / Mind Reader page
# -----------------------------------------------------------------------------


def page_mind_reader(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """AI/Mind Reader tab showing shift creator's thought process analysis."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Check if we have long_df data
    long_df = scenario.get_dataset("long_df")
    if long_df is None or long_df.empty:
        return create_missing_data_message(
            tab_name="🧠 AI / Mind Reader",
            required_files=["intermediate_data.parquet (long_df)"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )

    # Try to get cached analysis first
    cached_analysis = scenario.get_dataset("creator_mind_analysis")
    if not cached_analysis:
        # Try alternative cache keys
        cached_analysis = scenario.get_dataset("mind_reader_analysis")

    if cached_analysis:
        # Display cached results
        return _render_mind_reader_from_cache(cached_analysis)

    # If no cache, provide information about the feature
    return html.Div([
        html.H3("🧠 AI / Mind Reader"),
        html.P("シフト作成者の思考プロセスを逆算し、「なぜこの選択をしたのか」を解明します。"),
        html.Hr(),

        html.Div([
            html.H4("AI Mind Reader の3ステップロジック"),
            html.Ol([
                html.Li("意思決定ポイント再構築: 各スロットで誰が選ばれたかを時系列で再現"),
                html.Li("選好関数逆算: LightGBM Rankerで作成者の重視要素を学習"),
                html.Li("思考プロセス模倣: 決定木で判断フローを可視化"),
            ]),
        ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),

        html.Hr(),

        # Data info
        html.Div([
            _create_kpi_card("データ行数", f"{len(long_df):,} 行"),
            _create_kpi_card("職員数", f"{long_df['staff'].nunique() if 'staff' in long_df.columns else 0} 人"),
            _create_kpi_card("分析期間", f"{long_df['ds'].min().date()} ~ {long_df['ds'].max().date()}" if 'ds' in long_df.columns else "N/A"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.Hr(),

        html.P("⚠️ 注意: AI/Mind Reader タブの完全な実装には以下が必要です：",
               style={"color": "#856404", "backgroundColor": "#fff3cd", "padding": "15px", "borderRadius": "5px", "border": "1px solid #ffeaa7"}),

        html.Ul([
            html.Li("shift_suite.tasks.shift_mind_reader モジュール"),
            html.Li("LightGBM ライブラリ (pip install lightgbm)"),
            html.Li("scikit-learn ライブラリ"),
        ], style={"marginLeft": "40px"}),

        html.P("現在は creator_mind_analysis.json または mind_reader_analysis.json キャッシュファイルがある場合のみ結果を表示できます。"),
    ])


def _create_feature_importance_section(importance_list: list) -> List:
    """Create feature importance section with chart and top 3 KPI cards."""
    section_content = []

    if not isinstance(importance_list, list) or len(importance_list) == 0:
        return section_content

    # Create importance DataFrame
    importance_df = pd.DataFrame(importance_list)

    # Create horizontal bar chart
    fig = px.bar(
        importance_df.head(10),
        x="importance",
        y="feature",
        orientation="h",
        title="作成者が重視する要素 TOP10 (LightGBM Ranker)",
        labels={"feature": "要素", "importance": "重要度"},
        color="importance",
        color_continuous_scale="Viridis",
    )
    fig.update_layout(height=400, yaxis={'categoryorder':'total ascending'})

    section_content.extend([
        html.H4("🎯 作成者の選好関数"),
        html.P("シフト作成時に作成者が重視している要素を学習した結果です。"),
        dcc.Graph(figure=fig),
        html.Hr(),
    ])

    # Show top 3 as KPI cards
    if len(importance_list) >= 3:
        top3 = importance_list[:3]
        kpi_cards = html.Div([
            _create_kpi_card(
                f"#{i+1} {item.get('feature', 'N/A')}",
                f"{item.get('importance', 0):.1f}"
            )
            for i, item in enumerate(top3)
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"})

        section_content.extend([
            html.H5("重視要素トップ3"),
            kpi_cards,
            html.Hr(),
        ])

    return section_content


def _create_mind_reader_info_sections(analysis_data: dict) -> List:
    """Create thinking process tree, decision points, and statistics sections."""
    section_content = []

    # Thinking process tree
    if "thinking_process_tree" in analysis_data:
        tree_info = analysis_data["thinking_process_tree"]
        section_content.extend([
            html.H4("🌳 思考プロセスの決定木"),
            html.P("作成者の判断フローを決定木で模倣した結果です。"),
            html.Div([
                html.P(f"最大深さ: {tree_info.get('max_depth', 'N/A') if isinstance(tree_info, dict) else 'N/A'}"),
                html.P(f"特徴量数: {tree_info.get('n_features', 'N/A') if isinstance(tree_info, dict) else 'N/A'}"),
                html.P(f"サンプル数: {tree_info.get('n_samples', 'N/A') if isinstance(tree_info, dict) else 'N/A'}"),
            ], style={"backgroundColor": "#e8f4f8", "padding": "15px", "borderRadius": "5px", "marginBottom": "20px"}),
            html.Hr(),
        ])

    # Decision points summary
    if "decision_points_summary" in analysis_data:
        summary = analysis_data["decision_points_summary"]
        if isinstance(summary, dict):
            section_content.extend([
                html.H4("📋 意思決定ポイントサマリ"),
                html.Div([
                    _create_kpi_card("総意思決定回数", f"{summary.get('total_decisions', 0):,} 回"),
                    _create_kpi_card("平均選択肢数", f"{summary.get('avg_options', 0):.1f} 人"),
                    _create_kpi_card("分析精度", f"{summary.get('accuracy', 0):.1%}"),
                ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
                html.Hr(),
            ])

    # Detailed statistics
    if "statistics" in analysis_data:
        stats = analysis_data["statistics"]
        if isinstance(stats, dict):
            stats_df = pd.DataFrame([
                {"指標": k, "値": v}
                for k, v in stats.items()
            ])
            section_content.extend([
                html.H4("📊 分析統計"),
                _render_dataframe(stats_df, max_rows=20),
                html.Hr(),
            ])

    return section_content


def _render_mind_reader_from_cache(analysis_data: dict) -> html.Div:
    """Render mind reader analysis results from cached JSON data."""
    content = [
        html.H3("🧠 AI / Mind Reader"),
        html.P("シフト作成者の思考プロセス解読結果を表示します。"),
        html.Hr(),
    ]

    # Add feature importance section
    if "feature_importance" in analysis_data:
        content.extend(_create_feature_importance_section(analysis_data["feature_importance"]))

    # Add other info sections
    content.extend(_create_mind_reader_info_sections(analysis_data))

    # JSON preview
    content.extend([
        html.H4("分析結果JSON（プレビュー）"),
        html.Pre(
            json.dumps(analysis_data, ensure_ascii=False, indent=2)[:2000] + "...",
            style={"backgroundColor": "#f5f5f5", "padding": "15px", "borderRadius": "5px", "fontSize": "12px", "overflow": "auto"}
        ),
    ])

    return html.Div(content)


# -----------------------------------------------------------------------------
# Gap Analysis page
# -----------------------------------------------------------------------------


def _create_gap_summary_section(gap_summary: pd.DataFrame) -> List:
    """Create Gap Summary section with KPI cards, chart, and table."""
    section_content = []

    # Calculate total and average gap
    total_gap = 0.0
    if 'total_gap_hours' in gap_summary.columns:
        total_gap = gap_summary['total_gap_hours'].sum()
    elif 'gap_hours' in gap_summary.columns:
        total_gap = gap_summary['gap_hours'].sum()

    avg_gap = total_gap / len(gap_summary) if len(gap_summary) > 0 else 0.0

    # KPI cards
    section_content.extend([
        html.H4("📊 乖離サマリ"),
        html.Div([
            _create_kpi_card("総乖離時間", f"{total_gap:.1f} h"),
            _create_kpi_card("平均乖離", f"{avg_gap:.1f} h"),
            _create_kpi_card("分析対象", f"{len(gap_summary)} 項目"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
        html.Hr(),
    ])

    # Bar chart for gap summary by role
    if 'role' in gap_summary.columns:
        gap_col = 'total_gap_hours' if 'total_gap_hours' in gap_summary.columns else \
                 'gap_hours' if 'gap_hours' in gap_summary.columns else gap_summary.columns[-1]

        fig = px.bar(
            gap_summary,
            x='role',
            y=gap_col,
            title="職種別 乖離時間",
            labels={'role': '職種', gap_col: '乖離時間 (h)'},
            color=gap_col,
            color_continuous_scale='RdYlGn_r',  # Red for high gap
        )
        fig.update_layout(height=400)

        section_content.extend([
            html.H5("職種別乖離グラフ"),
            dcc.Graph(figure=fig),
            html.Hr(),
        ])

    # Summary table
    section_content.extend([
        html.H5("乖離サマリテーブル"),
        _render_dataframe(gap_summary, max_rows=20),
        html.Hr(),
    ])

    return section_content


def _create_gap_heatmap_section(gap_heatmap: pd.DataFrame) -> List:
    """Create Gap Heatmap section with visualization and data preview."""
    section_content = [
        html.H4("🔥 乖離ヒートマップ"),
        html.P("時間帯別の理想基準からの乖離度を可視化します。"),
    ]

    # Create heatmap visualization
    try:
        # If gap_heatmap has multiple columns, use heatmap
        if len(gap_heatmap.columns) > 1:
            fig = px.imshow(
                gap_heatmap,
                aspect="auto",
                color_continuous_scale="RdBu_r",  # Red for positive gap (excess), Blue for negative (shortage)
                labels=dict(x="日付", y="時間帯", color="乖離度"),
                title="基準乖離ヒートマップ"
            )
            fig.update_layout(height=500, margin=dict(l=20, r=20, t=60, b=20))
            section_content.append(dcc.Graph(figure=fig))
        else:
            # If single column, show as time series
            fig = px.line(
                gap_heatmap,
                x=gap_heatmap.index,
                y=gap_heatmap.columns[0],
                title="乖離度の推移",
                labels={'x': '時刻', 'y': '乖離度'}
            )
            section_content.append(dcc.Graph(figure=fig))
    except Exception as e:
        section_content.append(html.P(f"ヒートマップ可視化エラー: {str(e)}", style={"color": "#d9534f"}))

    # Data preview
    section_content.extend([
        html.Hr(),
        html.H5("乖離ヒートマップデータ（プレビュー）"),
        _render_dataframe(gap_heatmap.head(20), max_rows=20),
    ])

    return section_content


def page_gap_analysis(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Gap Analysis tab showing deviations from ideal standards."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Load gap analysis data
    gap_summary = scenario.get_dataset("gap_summary")
    gap_heatmap = scenario.get_dataset("gap_heatmap")

    # Check if any data is available
    if (gap_summary is None or (isinstance(gap_summary, pd.DataFrame) and gap_summary.empty)) and \
       (gap_heatmap is None or (isinstance(gap_heatmap, pd.DataFrame) and gap_heatmap.empty)):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="📉 基準乖離分析 (Gap Analysis)",
            required_files=["gap_summary.parquet", "gap_heatmap.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("基準乖離分析とは"),
                html.P("理想的な人員配置基準と実際の配置とのギャップを可視化します。"),
                html.Ul([
                    html.Li("gap_summary: 職種別の総乖離時間サマリ"),
                    html.Li("gap_heatmap: 時間帯別の乖離度ヒートマップ"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    # Initialize content with header
    content = [
        html.H3("📉 基準乖離分析 (Gap Analysis)"),
        html.P("理想基準からの乖離度を測定し、改善目標を明確化します。"),
        html.Hr(),
    ]

    # Add Gap Summary section
    if gap_summary is not None and isinstance(gap_summary, pd.DataFrame) and not gap_summary.empty:
        content.extend(_create_gap_summary_section(gap_summary))

    # Add Gap Heatmap section
    if gap_heatmap is not None and isinstance(gap_heatmap, pd.DataFrame) and not gap_heatmap.empty:
        content.extend(_create_gap_heatmap_section(gap_heatmap))

    # Check if any data sections were added
    if not content[3:]:
        content.append(html.P("表示可能な乖離データがありません。"))

    return html.Div(content)


# -----------------------------------------------------------------------------
# Individual Analysis page
# -----------------------------------------------------------------------------


def page_individual(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Individual staff analysis tab showing work patterns and synergy."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Check if we have long_df data
    long_df = scenario.get_dataset("long_df")
    if long_df is None or long_df.empty:
        return create_missing_data_message(
            tab_name="👤 職員個別分析",
            required_files=["intermediate_data.parquet (long_df)"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )

    # Basic staff information
    if 'staff' not in long_df.columns:
        return html.Div([
            html.H3("👤 職員個別分析"),
            html.P("データに staff カラムが見つかりません。"),
        ])

    all_staff = sorted(long_df['staff'].unique().tolist())
    if not all_staff:
        return html.Div([
            html.H3("👤 職員個別分析"),
            html.P("職員データがありません。"),
        ])

    # For now, show summary of first staff member
    selected_staff = all_staff[0]
    staff_df = long_df[long_df['staff'] == selected_staff].copy()

    # Calculate basic info
    total_shifts = len(staff_df)
    total_hours = total_shifts * 0.5  # 30分単位

    unique_dates = 0
    if 'ds' in staff_df.columns:
        unique_dates = staff_df['ds'].dt.date.nunique()

    avg_hours_per_day = total_hours / unique_dates if unique_dates > 0 else 0.0

    top_codes = {}
    if 'code' in staff_df.columns:
        top_codes = staff_df['code'].value_counts().head(3).to_dict()

    return html.Div([
        html.H3(f"👤 職員個別分析"),
        html.P("各職員の勤務パターンとシナジー分析を表示します。"),
        html.Hr(),

        html.Div([
            html.H5(f"選択職員: {selected_staff}"),
            html.P(f"（デフォルト表示: {len(all_staff)}人中の最初の職員）"),
        ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),

        html.Hr(),

        # Basic info cards
        html.H4("基本情報"),
        html.Div([
            _create_kpi_card("総勤務日数", f"{unique_dates} 日"),
            _create_kpi_card("総勤務時間", f"{total_hours:.1f} h"),
            _create_kpi_card("平均時間/日", f"{avg_hours_per_day:.1f} h"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.Hr(),

        # Top work codes
        html.H4("主な勤務コード"),
        html.Ul([
            html.Li(f"{code}: {count}回")
            for code, count in top_codes.items()
        ]) if top_codes else html.P("勤務コードデータがありません"),

        html.Hr(),

        html.P("⚠️ 注意: 完全なシナジー分析機能は shift_suite.tasks.analyzers.synergy モジュールが必要です。",
               style={"color": "#856404", "backgroundColor": "#fff3cd", "padding": "15px", "borderRadius": "5px"}),
    ])


# -----------------------------------------------------------------------------
# Team Analysis page
# -----------------------------------------------------------------------------


def page_team(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Team analysis tab showing dynamic team detection and collaboration patterns."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Check if we have long_df data
    long_df = scenario.get_dataset("long_df")
    if long_df is None or long_df.empty:
        return create_missing_data_message(
            tab_name="👥 チーム分析",
            required_files=["intermediate_data.parquet (long_df)"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )

    # Basic team information
    if 'staff' not in long_df.columns:
        return html.Div([
            html.H3("👥 チーム分析"),
            html.P("データに staff カラムが見つかりません。"),
        ])

    total_staff = long_df['staff'].nunique()

    # Calculate co-working patterns
    unique_dates = 0
    if 'ds' in long_df.columns:
        unique_dates = long_df['ds'].dt.date.nunique()

    return html.Div([
        html.H3("👥 チーム分析"),
        html.P("動的チーム抽出とチーム動態分析を表示します。"),
        html.Hr(),

        html.Div([
            html.H4("チーム分析の機能"),
            html.Ul([
                html.Li("共働関係の検出: 実際に一緒に働いている職員の組み合わせを特定"),
                html.Li("チーム結束度: コミュニティ検出アルゴリズムでチームを自動抽出"),
                html.Li("シナジー分析: チーム内の相性と協力パターンを可視化"),
            ]),
        ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),

        html.Hr(),

        html.H4("データサマリ"),
        html.Div([
            _create_kpi_card("総職員数", f"{total_staff} 人"),
            _create_kpi_card("分析日数", f"{unique_dates} 日"),
            _create_kpi_card("総シフト数", f"{len(long_df):,} 行"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.Hr(),

        html.P("⚠️ 注意: 完全なチーム分析機能は shift_suite.tasks.analyzers.team_dynamics モジュールが必要です。",
               style={"color": "#856404", "backgroundColor": "#fff3cd", "padding": "15px", "borderRadius": "5px"}),
    ])


# -----------------------------------------------------------------------------
# Fatigue Analysis page
# -----------------------------------------------------------------------------


def _create_fatigue_summary_section(fatigue_score: pd.DataFrame) -> List:
    """Create fatigue summary KPI cards and TOP20 chart."""
    section_content = []

    if 'total_fatigue' not in fatigue_score.columns:
        return section_content

    # Calculate summary statistics
    avg_fatigue = fatigue_score['total_fatigue'].mean()
    max_fatigue = fatigue_score['total_fatigue'].max()
    high_risk_count = len(fatigue_score[fatigue_score['total_fatigue'] > 70])

    section_content.extend([
        html.H4("疲労スコアサマリ"),
        html.Div([
            _create_kpi_card("平均疲労スコア", f"{avg_fatigue:.1f}"),
            _create_kpi_card("最大疲労スコア", f"{max_fatigue:.1f}"),
            _create_kpi_card("高リスク職員", f"{high_risk_count} 人"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
        html.Hr(),
    ])

    # Top fatigued staff chart
    top_fatigued = fatigue_score.nlargest(20, 'total_fatigue')

    fig = px.bar(
        top_fatigued,
        x='staff' if 'staff' in top_fatigued.columns else top_fatigued.index,
        y='total_fatigue',
        title="疲労スコア TOP20",
        labels={'staff': '職員', 'total_fatigue': '総合疲労スコア'},
        color='total_fatigue',
        color_continuous_scale='Reds',
    )
    fig.update_layout(height=400)

    section_content.extend([
        html.H4("疲労スコア TOP20"),
        dcc.Graph(figure=fig),
        html.Hr(),
    ])

    return section_content


def page_fatigue(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Fatigue analysis tab showing 6-element fatigue evaluation."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load fatigue score data
    fatigue_score = scenario.get_dataset("fatigue_score")

    if fatigue_score is None or (isinstance(fatigue_score, pd.DataFrame) and fatigue_score.empty):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="😴 疲労分析",
            required_files=["fatigue_score.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("疲労分析の6要素"),
                html.Ol([
                    html.Li("連続勤務疲労: 連続して働いた日数による疲労"),
                    html.Li("夜勤疲労: 夜間勤務による生体リズムへの影響"),
                    html.Li("長時間勤務疲労: 1日の労働時間による疲労"),
                    html.Li("休憩不足疲労: 適切な休憩が取れていない場合の疲労"),
                    html.Li("不規則勤務疲労: 勤務時間帯が不規則な場合の疲労"),
                    html.Li("総合疲労スコア: 上記5要素を統合した総合指標"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    # Display fatigue data
    content = [
        html.H3("😴 疲労分析"),
        html.P("6要素疲労評価に基づく職員の疲労度を分析します。"),
        html.Hr(),
    ]

    # Add summary section
    content.extend(_create_fatigue_summary_section(fatigue_score))

    # Data table
    content.extend([
        html.H4("疲労スコア詳細データ"),
        _render_dataframe(fatigue_score, max_rows=20),
    ])

    return html.Div(content)


# -----------------------------------------------------------------------------
# Leave Analysis page
# -----------------------------------------------------------------------------


def page_leave(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Leave analysis tab showing vacation/leave patterns."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load leave analysis data
    leave_analysis = scenario.get_dataset("leave_analysis")
    leave_ratio = scenario.get_dataset("leave_ratio_breakdown")

    if (leave_analysis is None or (isinstance(leave_analysis, pd.DataFrame) and leave_analysis.empty)) and \
       (leave_ratio is None or (isinstance(leave_ratio, pd.DataFrame) and leave_ratio.empty)):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="🏖️ 休暇分析",
            required_files=["leave_analysis.csv", "leave_ratio_breakdown.csv"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("休暇分析の目的"),
                html.P("職員の休暇取得パターンを分析し、ワークライフバランスの改善に役立てます。"),
                html.Ul([
                    html.Li("休暇取得率の可視化"),
                    html.Li("休暇取得が少ない職員の特定"),
                    html.Li("休暇タイプ別（有給/特別/病気）の分析"),
                    html.Li("月別休暇取得推移の把握"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    content = [
        html.H3("🏖️ 休暇分析"),
        html.P("職員の休暇取得パターンを分析します。"),
        html.Hr(),
    ]

    # Leave analysis data
    if leave_analysis is not None and isinstance(leave_analysis, pd.DataFrame) and not leave_analysis.empty:
        content.extend([
            html.H4("休暇分析結果"),
            _render_dataframe(leave_analysis, max_rows=20),
            html.Hr(),
        ])

    # Leave ratio breakdown
    if leave_ratio is not None and isinstance(leave_ratio, pd.DataFrame) and not leave_ratio.empty:
        content.extend([
            html.H4("休暇比率内訳"),
            _render_dataframe(leave_ratio, max_rows=20),
            html.Hr(),
        ])

    if len(content) == 3:  # Only header content
        content.append(html.P("表示可能な休暇データがありません。"))

    return html.Div(content)


# -----------------------------------------------------------------------------
# Fairness Analysis page
# -----------------------------------------------------------------------------


def page_fairness(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Fairness analysis tab showing work hour distribution and Jain's Index."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load fairness data
    fairness_before = scenario.get_dataset("fairness_before")
    fairness_after = scenario.get_dataset("fairness_after")

    if (fairness_before is None or (isinstance(fairness_before, pd.DataFrame) and fairness_before.empty)) and \
       (fairness_after is None or (isinstance(fairness_after, pd.DataFrame) and fairness_after.empty)):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="⚖️ 公平性分析",
            required_files=["fairness_before.parquet", "fairness_after.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("公平性分析について"),
                html.P("Jain's Index を用いて勤務時間の公平性を評価します。"),
                html.Ul([
                    html.Li("Jain's Index: 0~1の値で、1に近いほど公平"),
                    html.Li("職員間の勤務時間分布を可視化"),
                    html.Li("改善前後の比較が可能"),
                    html.Li("不公平な配置の検出と改善提案"),
                ]),
                html.Hr(),
                html.H5("Jain's Index の計算式"),
                html.P("J = (Σx_i)² / (n * Σx_i²)"),
                html.P("x_i: 各職員の勤務時間, n: 職員数", style={"fontSize": "12px", "color": "#666"}),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    content = [
        html.H3("⚖️ 公平性分析"),
        html.P("勤務時間の公平性を Jain's Index で評価します。"),
        html.Hr(),
    ]

    # Fairness before
    if fairness_before is not None and isinstance(fairness_before, pd.DataFrame) and not fairness_before.empty:
        jain_before = _calculate_jain_index(fairness_before)

        content.extend([
            html.H4("改善前の公平性"),
            html.Div([
                _create_kpi_card("Jain's Index", f"{jain_before:.3f}"),
                _create_kpi_card("対象職員数", f"{len(fairness_before)} 人"),
            ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
            _render_dataframe(fairness_before, max_rows=10),
            html.Hr(),
        ])

    # Fairness after
    if fairness_after is not None and isinstance(fairness_after, pd.DataFrame) and not fairness_after.empty:
        jain_after = _calculate_jain_index(fairness_after)

        improvement = ""
        if fairness_before is not None and not fairness_before.empty:
            jain_before_val = _calculate_jain_index(fairness_before)
            improvement = f" (改善: +{(jain_after - jain_before_val):.3f})"

        content.extend([
            html.H4("改善後の公平性"),
            html.Div([
                _create_kpi_card("Jain's Index", f"{jain_after:.3f}{improvement}"),
                _create_kpi_card("対象職員数", f"{len(fairness_after)} 人"),
            ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),
            _render_dataframe(fairness_after, max_rows=10),
            html.Hr(),
        ])

    if len(content) == 3:  # Only header content
        content.append(html.P("表示可能な公平性データがありません。"))

    return html.Div(content)


def _calculate_jain_index(df: pd.DataFrame) -> float:
    """Calculate Jain's Index for fairness evaluation."""
    if df.empty:
        return 0.0

    # Try common column names for work hours
    work_hours_col = None
    for col in ['work_hours', 'total_hours', 'hours', 'total_work_hours']:
        if col in df.columns:
            work_hours_col = col
            break

    if work_hours_col is None:
        # Try first numeric column
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            work_hours_col = numeric_cols[0]
        else:
            return 0.0

    values = df[work_hours_col].values
    n = len(values)
    if n == 0:
        return 0.0

    numerator = (values.sum()) ** 2
    denominator = n * (values ** 2).sum()

    return float(numerator / denominator) if denominator > 0 else 0.0


# -----------------------------------------------------------------------------
# Optimization Analysis page
# -----------------------------------------------------------------------------


def page_optimization(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Optimization analysis tab showing optimization score time series."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load optimization score data
    opt_score = scenario.get_dataset("optimization_score_time")

    if opt_score is None or (isinstance(opt_score, pd.DataFrame) and opt_score.empty):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="🎯 最適化分析",
            required_files=["optimization_score_time.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("最適化分析について"),
                html.P("シフト最適化のスコアを時系列で表示し、最適化の効果を測定します。"),
                html.Ul([
                    html.Li("時系列での最適化スコア推移"),
                    html.Li("ピーク時の特定"),
                    html.Li("改善トレンドの可視化"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    # Display optimization score data
    content = [
        html.H3("🎯 最適化分析"),
        html.P("シフト最適化のスコアを時系列で表示します。"),
        html.Hr(),
    ]

    # Time series graph
    try:
        fig = px.line(
            opt_score,
            x=opt_score.index if hasattr(opt_score, 'index') else range(len(opt_score)),
            y=opt_score.columns[0] if len(opt_score.columns) > 0 else None,
            title="最適化スコアの推移",
            labels={'x': '日付', 'y': 'スコア'}
        )
        fig.update_layout(height=400)

        content.extend([
            html.H4("スコア推移"),
            dcc.Graph(figure=fig),
            html.Hr(),
        ])
    except Exception as e:
        content.append(html.P(f"グラフ生成エラー: {str(e)}", style={"color": "#d9534f"}))

    # Data table
    content.extend([
        html.H4("詳細データ"),
        _render_dataframe(opt_score, max_rows=20),
    ])

    return html.Div(content)


# -----------------------------------------------------------------------------
# Forecast Analysis page
# -----------------------------------------------------------------------------


def page_forecast(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Forecast analysis tab showing demand prediction results."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load forecast data
    forecast_df = scenario.get_dataset("forecast")
    forecast_json = scenario.get_dataset("forecast_json")
    demand_series = scenario.get_dataset("demand_series")

    if (forecast_df is None or (isinstance(forecast_df, pd.DataFrame) and forecast_df.empty)) and \
       (forecast_json is None) and \
       (demand_series is None or (isinstance(demand_series, pd.DataFrame) and demand_series.empty)):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="📈 需要予測",
            required_files=["forecast.parquet", "forecast.json", "demand_series.csv"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("需要予測について"),
                html.P("将来の人員需要を予測し、事前の人員計画に役立てます。"),
                html.Ul([
                    html.Li("時系列需要予測"),
                    html.Li("季節性・トレンド分析"),
                    html.Li("予測信頼区間"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    content = [
        html.H3("📈 需要予測"),
        html.P("将来の人員需要を予測します。"),
        html.Hr(),
    ]

    # Demand series graph
    if demand_series is not None and isinstance(demand_series, pd.DataFrame) and not demand_series.empty:
        try:
            fig = px.line(
                demand_series,
                x=demand_series.index if hasattr(demand_series, 'index') else range(len(demand_series)),
                y=demand_series.columns[0] if len(demand_series.columns) > 0 else None,
                title="需要系列",
                labels={'x': '時刻', 'y': '需要'}
            )
            fig.update_layout(height=400)

            content.extend([
                html.H4("需要系列"),
                dcc.Graph(figure=fig),
                html.Hr(),
            ])
        except Exception:
            pass

    # Forecast results table
    if forecast_df is not None and isinstance(forecast_df, pd.DataFrame) and not forecast_df.empty:
        content.extend([
            html.H4("予測結果"),
            _render_dataframe(forecast_df, max_rows=20),
            html.Hr(),
        ])

    if len(content) == 3:  # Only header content
        content.append(html.P("表示可能な予測データがありません。"))

    return html.Div(content)


# -----------------------------------------------------------------------------
# Hire Plan page
# -----------------------------------------------------------------------------


def page_hire_plan(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Hire plan tab showing recruitment planning."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load hire plan data
    hire_plan = scenario.get_dataset("hire_plan")

    if hire_plan is None or (isinstance(hire_plan, pd.DataFrame) and hire_plan.empty):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="👔 採用計画",
            required_files=["hire_plan.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("採用計画について"),
                html.P("不足を解消するための採用計画を提示し、採用人数の根拠を示します。"),
                html.Ul([
                    html.Li("職種別採用推奨人数"),
                    html.Li("優先度順採用計画"),
                    html.Li("コスト試算"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    content = [
        html.H3("👔 採用計画"),
        html.P("不足を解消するための採用計画を提示します。"),
        html.Hr(),
    ]

    # Display hire plan data
    content.extend([
        html.H4("採用計画データ"),
        _render_dataframe(hire_plan, max_rows=20),
    ])

    return html.Div(content)


# -----------------------------------------------------------------------------
# Cost Analysis page
# -----------------------------------------------------------------------------


def page_cost(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Cost analysis tab showing labor cost visualization."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Try to load cost data
    daily_cost = scenario.get_dataset("daily_cost")
    cost_benefit = scenario.get_dataset("cost_benefit")

    if (daily_cost is None or (isinstance(daily_cost, pd.DataFrame) and daily_cost.empty)) and \
       (cost_benefit is None or (isinstance(cost_benefit, pd.DataFrame) and cost_benefit.empty)):
        # Create error message with helper function
        error_msg = create_missing_data_message(
            tab_name="💰 コスト分析",
            required_files=["daily_cost.parquet", "cost_benefit.parquet"],
            additional_info="データがアップロードされたZIPに含まれていることを確認してください。"
        )
        # Add explanation section
        explanation = html.Div([
            html.Hr(),
            html.Div([
                html.H4("コスト分析について"),
                html.P("人件費を可視化し、コスト最適化の根拠を提供します。"),
                html.Ul([
                    html.Li("日次コスト推移"),
                    html.Li("コスト効果分析"),
                    html.Li("ROI計算"),
                ]),
            ], style={"marginTop": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"}),
        ])
        return html.Div([error_msg, explanation])

    content = [
        html.H3("💰 コスト分析"),
        html.P("人件費とコスト効果を分析します。"),
        html.Hr(),
    ]

    # Daily cost graph
    if daily_cost is not None and isinstance(daily_cost, pd.DataFrame) and not daily_cost.empty:
        try:
            fig = px.line(
                daily_cost,
                x=daily_cost.index if hasattr(daily_cost, 'index') else range(len(daily_cost)),
                y=daily_cost.columns[0] if len(daily_cost.columns) > 0 else None,
                title="日次コスト推移",
                labels={'x': '日付', 'y': 'コスト (円)'}
            )
            fig.update_layout(height=400)

            content.extend([
                html.H4("日次コスト"),
                dcc.Graph(figure=fig),
                html.Hr(),
            ])
        except Exception:
            pass

    # Cost benefit analysis
    if cost_benefit is not None and isinstance(cost_benefit, pd.DataFrame) and not cost_benefit.empty:
        content.extend([
            html.H4("コスト効果分析"),
            _render_dataframe(cost_benefit, max_rows=20),
            html.Hr(),
        ])

    if len(content) == 3:  # Only header content
        content.append(html.P("表示可能なコストデータがありません。"))

    return html.Div(content)


# -----------------------------------------------------------------------------
# Summary Report page
# -----------------------------------------------------------------------------


def _collect_summary_data(scenario: ScenarioData) -> Dict[str, Any]:
    """Collect all summary metrics and findings for the summary report."""
    summary_data = {}

    # Basic metrics
    summary_data['total_shortage_hours'] = _calculate_total_shortage_hours(scenario.shortage_time)
    summary_data['total_staff'] = len(scenario.roles) if scenario.roles else 0

    # Date range
    if not scenario.heat_staff.empty and len(scenario.heat_staff.columns) > 0:
        summary_data['date_range'] = f"{scenario.heat_staff.columns[0]} ~ {scenario.heat_staff.columns[-1]}"
    else:
        summary_data['date_range'] = "N/A"

    # Fairness score
    fairness_before = scenario.get_dataset("fairness_before")
    if fairness_before is not None and isinstance(fairness_before, pd.DataFrame) and not fairness_before.empty:
        summary_data['fairness_score'] = _calculate_jain_index(fairness_before)
    else:
        summary_data['fairness_score'] = None

    # Top fatigued staff
    top_fatigue_staff = []
    fatigue_score = scenario.get_dataset("fatigue_score")
    if fatigue_score is not None and isinstance(fatigue_score, pd.DataFrame) and not fatigue_score.empty:
        if 'total_fatigue' in fatigue_score.columns:
            top3 = fatigue_score.nlargest(3, 'total_fatigue')
            top_fatigue_staff = top3['staff'].tolist() if 'staff' in top3.columns else top3.index.tolist()
    summary_data['top_fatigue_staff'] = top_fatigue_staff

    # Key findings from blueprint
    key_findings = []
    blueprint_data = _blueprint_analysis_for_scenario(scenario)
    if blueprint_data and 'rules_df' in blueprint_data:
        rules_df = _ensure_dataframe(blueprint_data['rules_df'])
        if not rules_df.empty and '発見された法則' in rules_df.columns:
            strength_col = '法則の強度' if '法則の強度' in rules_df.columns else rules_df.columns[0]
            top_rules = rules_df.nlargest(3, strength_col) if strength_col in rules_df.columns else rules_df.head(3)
            key_findings = top_rules['発見された法則'].tolist()
    summary_data['key_findings'] = key_findings

    return summary_data


def page_summary(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Summary report tab showing integrated analysis results."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Collect all summary data
    data = _collect_summary_data(scenario)

    # Build content
    content = [
        html.H3("📄 統合サマリーレポート"),
        html.P("全分析結果の統合レポートです。"),
        html.Hr(),

        # Executive Summary
        html.H4("🎯 エグゼクティブサマリ"),
        html.Div([
            _create_kpi_card("総不足時間", f"{data['total_shortage_hours']:.1f} h"),
            _create_kpi_card("総職員数", f"{data['total_staff']} 人"),
            _create_kpi_card("分析期間", data['date_range']),
            _create_kpi_card("公平性", f"{data['fairness_score']:.2f}" if data['fairness_score'] else "N/A"),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.Hr(),
    ]

    # Key findings
    if data['key_findings']:
        content.extend([
            html.H4("🔍 主要な発見事項"),
            html.Ul([html.Li(finding) for finding in data['key_findings']]),
            html.Hr(),
        ])

    # Recommendations
    recommendations = []
    if data['total_shortage_hours'] > 100:
        recommendations.append("⚠️ 総不足時間が100時間を超えています。採用を検討してください。")
    if data['fairness_score'] and data['fairness_score'] < 0.8:
        recommendations.append("⚠️ 公平性スコアが低いです。勤務時間の均等化を検討してください。")
    if data['top_fatigue_staff']:
        staff_list = ', '.join([str(s) for s in data['top_fatigue_staff'][:3]])
        recommendations.append(f"⚠️ 疲労度が高い職員がいます: {staff_list}")
    if not recommendations:
        recommendations.append("✅ 特に緊急の課題は検出されませんでした。")

    content.extend([
        html.H4("💡 推奨事項"),
        html.Ul([html.Li(rec) for rec in recommendations]),
    ])

    return html.Div(content)


def page_reports(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """
    レポート生成タブ - PowerPointレポートと各種エクスポート機能を提供

    Args:
        session: SessionData オブジェクト
        metadata: メタデータ辞書

    Returns:
        レポートタブのDash HTMLコンポーネント
    """
    return html.Div([
        html.H3("📄 レポート生成"),
        html.P("分析結果を各種形式でエクスポートできます。"),
        html.Hr(),

        # PowerPointレポート
        html.H4("📊 PowerPointレポート"),
        html.P("全分析結果をPowerPoint形式でエクスポートします。", style={"color": "#666"}),
        html.Div([
            html.P("🚧 この機能は現在開発中です。", style={"padding": "15px", "backgroundColor": "#fff3cd", "border": "1px solid #ffc107", "borderRadius": "5px"}),
            html.P("実装予定の機能:", style={"marginTop": "15px", "fontWeight": "bold"}),
            html.Ul([
                html.Li("エグゼクティブサマリースライド"),
                html.Li("不足時間分析グラフ"),
                html.Li("公平性指標の可視化"),
                html.Li("疲労度・休暇分析チャート"),
                html.Li("推奨アクションサマリー")
            ])
        ], style={"padding": "20px", "border": "1px solid #ddd", "borderRadius": "5px", "marginBottom": "20px"}),

        # CSVエクスポート
        html.Hr(),
        html.H4("📑 CSVエクスポート"),
        html.P("データテーブルをCSV形式でダウンロードします。", style={"color": "#666"}),
        html.Div([
            html.P("エクスポート可能なデータ:", style={"fontWeight": "bold"}),
            html.Ul([
                html.Li("不足時間データ (shortage_time.parquet)"),
                html.Li("個人別勤務データ (long_df)"),
                html.Li("ヒートマップデータ (heat_staff, heat_ratio)"),
                html.Li("公平性指標 (fairness_before, fairness_after)"),
                html.Li("疲労度スコア (fatigue_score)"),
                html.Li("コスト分析 (daily_cost, cost_benefit)")
            ]),
            html.P("🚧 ダウンロード機能は今後実装予定です。",
                   style={"padding": "10px", "backgroundColor": "#e7f3ff", "border": "1px solid #2196F3",
                          "borderRadius": "5px", "marginTop": "15px"})
        ], style={"padding": "20px", "border": "1px solid #ddd", "borderRadius": "5px"}),

        # 利用可能なデータセット情報
        html.Hr(),
        html.H4("📦 利用可能なデータセット"),
        html.P("現在のセッションには以下のデータが含まれています:", style={"marginBottom": "10px"}),
        _render_available_datasets(session, metadata)
    ])


def _render_available_datasets(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """利用可能なデータセットのリストを表示"""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # 利用可能なデータセットをチェック
    available_datasets = []
    dataset_checks = {
        "不足時間データ": "shortage_time",
        "個人別データ": "long_df",
        "ヒートマップ": "heat_staff",
        "公平性指標": "fairness_before",
        "疲労度スコア": "fatigue_score",
        "休暇分析": "leave_analysis",
        "コスト分析": "daily_cost",
        "最適化スコア": "optimization_score_time",
        "需要予測": "forecast",
        "採用計画": "hire_plan"
    }

    for label, attr_name in dataset_checks.items():
        if hasattr(scenario, attr_name):
            data = getattr(scenario, attr_name, None)
            if data is not None:
                if isinstance(data, pd.DataFrame) and not data.empty:
                    available_datasets.append(html.Li(f"✅ {label}"))
                elif isinstance(data, dict) and len(data) > 0:
                    available_datasets.append(html.Li(f"✅ {label}"))
                else:
                    available_datasets.append(html.Li(f"⚠️ {label} (データなし)", style={"color": "#999"}))
            else:
                available_datasets.append(html.Li(f"❌ {label} (利用不可)", style={"color": "#ccc"}))
        else:
            available_datasets.append(html.Li(f"❌ {label} (利用不可)", style={"color": "#ccc"}))

    return html.Ul(available_datasets, style={"columnCount": "2", "columnGap": "20px"})


# -----------------------------------------------------------------------------
# Heatmap page
# -----------------------------------------------------------------------------


def _create_heatmap_figure(scenario: ScenarioData, metadata: Optional[dict]) -> Any:
    """Create heatmap figure with responsive design and dynamic color scheme."""
    # Phase 2-2/2-3 完全実装: ResponsiveVisualizationEngineを実際に使用
    device_type = metadata.get("device_type", "desktop") if metadata else "desktop"

    # Phase 3-5: カラースキームの動的取得
    color_scheme_key = metadata.get("color_scheme", DEFAULT_COLOR_SCHEME) if metadata else DEFAULT_COLOR_SCHEME
    color_scheme = COLOR_SCHEMES.get(color_scheme_key, COLOR_SCHEMES[DEFAULT_COLOR_SCHEME])
    color_scale = color_scheme['scale']

    # Get visualization engine
    viz_engine = get_visualization_engine()

    if scenario.heat_staff.empty:
        return _empty_figure("データがありません")

    # Phase 2-2: レスポンシブデザインの実装
    if viz_engine is not None and VISUALIZATION_ENGINE_AVAILABLE:
        # 旧システムのResponsiveVisualizationEngineを使用
        fig = viz_engine.create_responsive_heatmap(
            data=scenario.heat_staff,
            title="全体ヒートマップ",
            device_type=device_type,
            progress_callback=None  # 進捗コールバックは現状では使用しない
        )
        # Phase 3-5: カラースケールとz範囲を手動で適用（動的カラースキーム）
        if hasattr(fig.data[0], 'colorscale'):
            fig.data[0].colorscale = color_scale
            fig.data[0].zmin = 0
            fig.data[0].zmax = scenario.heat_settings.zmax_default
    else:
        # Phase 3-5: フォールバック（動的カラースキーム適用）
        fig = px.imshow(
            scenario.heat_staff,
            aspect="auto",
            color_continuous_scale=color_scale,
            zmin=0,
            zmax=scenario.heat_settings.zmax_default,
            labels=dict(x="日付", y="時間帯", color="配置人数"),
            title="全体ヒートマップ"
        )
        fig.update_layout(
            height=500,
            margin=dict(l=20, r=20, t=60, b=20),
        )

    return fig


def _create_heatmap_stats(heat_staff: pd.DataFrame) -> html.Div:
    """Create summary statistics display for heatmap."""
    if heat_staff.empty:
        return html.Div()

    max_staff = float(heat_staff.max().max())
    min_staff = float(heat_staff.min().min())
    avg_staff = float(heat_staff.mean().mean())

    return html.Div([
        html.Div([
            html.Span("最大配置: ", style={"fontWeight": "bold"}),
            html.Span(f"{max_staff:.1f} 人"),
        ], style={"marginRight": "20px", "display": "inline-block"}),
        html.Div([
            html.Span("最小配置: ", style={"fontWeight": "bold"}),
            html.Span(f"{min_staff:.1f} 人"),
        ], style={"marginRight": "20px", "display": "inline-block"}),
        html.Div([
            html.Span("平均配置: ", style={"fontWeight": "bold"}),
            html.Span(f"{avg_staff:.1f} 人"),
        ], style={"display": "inline-block"}),
    ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"})


def page_heatmap(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Heatmap visualization tab showing staff allocation heat maps."""
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Check if we have heatmap data
    if scenario.heat_staff.empty:
        return html.Div([
            html.H3("ヒートマップ"),
            html.P("ヒートマップデータがありません。heat_ALL.parquet ファイルが必要です。"),
        ])

    # Create heatmap figure
    fig = _create_heatmap_figure(scenario, metadata)

    # Create summary statistics
    stats = _create_heatmap_stats(scenario.heat_staff)

    # Phase 2-3: 進捗表示の統合
    return html.Div([
        html.H3("🔥 ヒートマップ"),
        html.P("時間帯別・日付別の配置人数を可視化します。"),
        html.Hr(),
        stats,
        # Phase 2-3: 進捗表示コンポーネントでグラフをラップ
        dcc.Loading(
            id="loading-heatmap",
            type="default",
            children=dcc.Graph(figure=fig, config={'displayModeBar': True}),
            color="#2196f3"
        ),
        html.Hr(),
        html.P(
            "ヒートマップでは、色の濃さが配置人数を表します。青い領域ほど配置が多く、薄い領域は配置が少ないことを示します。",
            style={"fontSize": "12px", "color": "#666"}
        ),
    ])


# -----------------------------------------------------------------------------
# Overview page
# -----------------------------------------------------------------------------


def _create_kpi_card(title: str, value: str) -> html.Div:
    """Create a KPI card component with accessibility support (Phase 3-3)."""
    return html.Div(
        [
            html.Div(
                title,
                id=f"kpi-title-{title.replace(' ', '-').lower()}",
                style={"fontSize": "14px", "color": "#666", "marginBottom": "8px"}
            ),
            html.Div(
                value,
                style={"fontSize": "28px", "fontWeight": "bold", "color": "#333"},
                **{"aria-label": f"{title}: {value}"}
            ),
        ],
        style={
            "backgroundColor": "white",
            "padding": "20px",
            "borderRadius": "8px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "minWidth": "180px",
            "flex": "1",
        },
        role="region",
        **{"aria-label": f"KPIカード: {title}"}
    )


def _calculate_overview_kpis(scenario: ScenarioData) -> Dict[str, Any]:
    """Calculate key performance indicators for overview dashboard."""
    kpis = {}

    # Total shortage hours
    kpis['total_shortage_hours'] = _calculate_total_shortage_hours(scenario.shortage_time)

    # Total staff
    kpis['total_staff'] = len(scenario.roles) if scenario.roles else 0

    # Date range
    date_range = "N/A"
    if not scenario.heat_staff.empty and len(scenario.heat_staff.columns) > 0:
        date_range = f"{scenario.heat_staff.columns[0]} ~ {scenario.heat_staff.columns[-1]}"
    kpis['date_range'] = date_range

    # Average daily staff
    avg_daily_staff = 0.0
    long_df = scenario.get_dataset("long_df")
    if long_df is not None and not long_df.empty and 'ds' in long_df.columns and 'staff' in long_df.columns:
        try:
            avg_daily_staff = long_df.groupby(long_df['ds'].dt.date)['staff'].nunique().mean()
        except Exception:
            pass
    kpis['avg_daily_staff'] = avg_daily_staff

    return kpis


def _create_overview_charts(scenario: ScenarioData) -> List:
    """Create shortage charts for overview dashboard (role-based and employment-based)."""
    charts = []

    # Role-based shortage chart
    if not scenario.shortage_role_summary.empty and 'role' in scenario.shortage_role_summary.columns:
        role_df = scenario.shortage_role_summary
        if 'lack_h' in role_df.columns:
            top_roles = role_df.nlargest(10, 'lack_h') if len(role_df) > 10 else role_df
            role_chart = dcc.Graph(
                figure=px.bar(
                    top_roles,
                    x='role',
                    y='lack_h',
                    title="職種別 不足時間 TOP10",
                    labels={'role': '職種', 'lack_h': '不足時間 (h)'},
                    color='lack_h',
                    color_continuous_scale='Reds',
                ),
                config={'displayModeBar': False}
            )
            charts.append(html.Div([role_chart], style={"flex": "1", "minWidth": "400px"}, role="img", **{'aria-label': '職種別不足時間グラフ'}))

    # Employment-based shortage chart
    if not scenario.shortage_employment_summary.empty and 'employment' in scenario.shortage_employment_summary.columns:
        emp_df = scenario.shortage_employment_summary
        if 'lack_h' in emp_df.columns:
            emp_chart = dcc.Graph(
                figure=px.bar(
                    emp_df,
                    x='employment',
                    y='lack_h',
                    title="勤務形態別 不足時間",
                    labels={'employment': '勤務形態', 'lack_h': '不足時間 (h)'},
                    color='lack_h',
                    color_continuous_scale='Oranges',
                ),
                config={'displayModeBar': False}
            )
            charts.append(html.Div([emp_chart], style={"flex": "1", "minWidth": "400px"}, role="img", **{'aria-label': '勤務形態別不足時間グラフ'}))

    return charts


def page_overview(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Overview dashboard tab showing key metrics and summaries."""
    start_time = time.time()

    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    # Calculate KPIs
    kpis = _calculate_overview_kpis(scenario)

    # Create KPI cards
    kpi_cards = html.Div(
        [
            _create_kpi_card("総不足時間", f"{kpis['total_shortage_hours']:.1f} h"),
            _create_kpi_card("分析期間", kpis['date_range']),
            _create_kpi_card("総職員数", f"{kpis['total_staff']} 人"),
            _create_kpi_card("平均配置", f"{kpis['avg_daily_staff']:.1f} 人/日"),
        ],
        style={"display": "flex", "gap": "20px", "marginBottom": "30px", "flexWrap": "wrap"},
    )

    # Create charts
    charts = _create_overview_charts(scenario)

    # Charts container with accessibility
    charts_div = html.Div(
        charts,
        style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
        role="region",
        **{'aria-label': 'グラフセクション'}
    ) if charts else html.P("グラフデータがありません。", role="status")

    # Log performance
    duration = time.time() - start_time
    log_performance("Overview Tab レンダリング", duration, {"scenario": scenario_name or "default"})

    # Return dashboard layout
    return html.Div(
        [
            html.H2("📊 概要ダッシュボード", **{'aria-level': '2'}),
            html.P("シフトシステム全体のKPIと基本統計を表示します。", role="doc-subtitle"),
            html.Hr(**{'aria-hidden': 'true'}),
            html.Div(kpi_cards, role="region", **{'aria-label': 'KPIカードセクション'}),
            html.Hr(**{'aria-hidden': 'true'}),
            dcc.Loading(
                id="loading-overview-charts",
                type="default",
                children=charts_div,
                color="#2196f3"
            ),
        ],
        role="article",
        **{'aria-label': '概要ダッシュボード'}
    )


# -----------------------------------------------------------------------------
# Shortage page
# -----------------------------------------------------------------------------


def page_shortage(session: SessionData, metadata: Optional[dict]) -> html.Div:
    scenario_name = metadata.get("scenario") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)

    if scenario.shortage_time.empty and scenario.shortage_role_summary.empty:
        return html.Div(
            [
                html.H3("不足データがありません"),
                html.P("不足関連のアーティファクトが見つかりませんでした。"),
            ]
        )

    total_lack_hours = _calculate_total_shortage_hours(scenario.shortage_time)
    cards = []
    if total_lack_hours > 0:
        cards.append(html.Div([html.H4("総不足時間"), html.P(f"{total_lack_hours:.1f} h")]))

    if not scenario.shortage_role_summary.empty:
        cards.append(
            html.Div(
                [
                    html.H4("職種別 不足時間"),
                    dcc.Graph(
                        figure=px.bar(
                            scenario.shortage_role_summary,
                            x="role",
                            y="lack_h",
                            labels={"role": "Role", "lack_h": "不足時間"},
                        )
                    ),
                ]
            )
        )

    if not scenario.shortage_employment_summary.empty:
        cards.append(
            html.Div(
                [
                    html.H4("勤務形態別 不足時間"),
                    dcc.Graph(
                        figure=px.bar(
                            scenario.shortage_employment_summary,
                            x="employment",
                            y="lack_h",
                            labels={"employment": "Employment", "lack_h": "不足時間"},
                        )
                    ),
                ]
            )
        )

    return html.Div(cards or [html.P("不足に関する集計がありません。")])


# -----------------------------------------------------------------------------
# Misc helpers for tests
# -----------------------------------------------------------------------------


def update_metadata_on_scenario(
    scenario_value: Optional[str], session_id: Optional[str], metadata: Optional[dict]
) -> Dict[str, object]:
    session = get_session(session_id)
    if session is None:
        return {}
    return session.metadata(scenario_value)


__all__ = [
    "HeatmapSettings",
    "ScenarioData",
    "SCENARIO_ARTIFACT_EXPECTATIONS",
    "SessionData",
    "_build_comparison_heatmap_figure",
    "_calculate_total_shortage_hours",
    "_collect_missing_artifacts",
    "_ensure_artifacts_from_root",
    "load_session_data_from_zip",
    "page_logic",
    "page_mind_reader",
    "page_gap_analysis",
    "page_individual",
    "page_team",
    "page_fatigue",
    "page_leave",
    "page_fairness",
    "page_optimization",
    "page_forecast",
    "page_hire_plan",
    "page_cost",
    "page_summary",
    "page_reports",
    "page_heatmap",
    "page_overview",
    "page_shortage",
    "page_blueprint",
    "register_session",
    "get_session",
    "get_dataset",
    "update_heatmap",
    "update_heatmap_comparison_panel",
    # Phase 1: Memory Management Integration
    "initialize_memory_manager",
    "get_memory_manager",
    "cleanup_expired_sessions",
    "start_session_cleanup",
    # Phase 2-2/2-3: Visualization Engine Integration
    "initialize_visualization_engine",
    "get_visualization_engine",
    "create_progress_indicator",
]
