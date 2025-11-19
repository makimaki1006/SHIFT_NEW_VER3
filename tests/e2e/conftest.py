"""Pytest configuration for E2E tests with multi-dataset support."""
import base64
from pathlib import Path
from typing import Dict, List

import pytest

from dash_app import load_session_data_from_zip

# Note: base64 is still needed for loaded_session fixture


# ==============================================================================
# Test Dataset Registry
# ==============================================================================

TEST_DATASETS = {
    "analysis_7": {
        "path": "data/e2e-fixtures/analysis_7.zip",
        "size_kb": 718,
        "files": 234,
        "description": "Original baseline dataset (Sept 2025)",
        "expected_scenarios": 3,
        "tags": ["baseline", "multi-scenario"]
    },
    "analysis_8": {
        "path": "data/e2e-fixtures/analysis_8.zip",
        "size_kb": 619,
        "files": 226,
        "description": "Analysis results #8 (Sept 10, 2025)",
        "expected_scenarios": 1,
        "tags": ["production", "single-scenario"]
    },
    "analysis_9": {
        "path": "data/e2e-fixtures/analysis_9.zip",
        "size_kb": 742,
        "files": 234,
        "description": "Analysis results #9 (Sept 10, 2025)",
        "expected_scenarios": 1,
        "tags": ["production", "single-scenario", "largest"]
    },
    "tennoh_august": {
        "path": "data/e2e-fixtures/tennoh_august.zip",
        "size_kb": 704,
        "files": 239,
        "description": "天王 August 2025 data",
        "expected_scenarios": 1,
        "tags": ["production", "tennoh", "regional"]
    },
    "ashikaga_august": {
        "path": "data/e2e-fixtures/ashikaga_august.zip",
        "size_kb": 696,
        "files": 230,
        "description": "足利 August 2025 data",
        "expected_scenarios": 1,
        "tags": ["production", "ashikaga", "regional"]
    }
}


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def base_url():
    """Base URL for the Dash application."""
    return "http://127.0.0.1:8055"


@pytest.fixture(scope="session")
def test_zip_path():
    """Path to the default test ZIP file (backwards compatibility)."""
    return "data/e2e-fixtures/analysis_results (7).zip"


@pytest.fixture(scope="session")
def all_test_datasets() -> Dict[str, Dict]:
    """Registry of all available test datasets."""
    return TEST_DATASETS


@pytest.fixture(scope="session")
def validate_test_data():
    """Validate that all test datasets exist and are accessible."""
    missing = []
    invalid = []

    for name, dataset in TEST_DATASETS.items():
        path = Path(dataset["path"])
        if not path.exists():
            missing.append((name, dataset["path"]))
        elif path.stat().st_size == 0:
            invalid.append((name, dataset["path"]))

    if missing or invalid:
        error_msg = []
        if missing:
            error_msg.append("Missing datasets:")
            for name, path in missing:
                error_msg.append(f"  - {name}: {path}")
        if invalid:
            error_msg.append("Invalid (0 byte) datasets:")
            for name, path in invalid:
                error_msg.append(f"  - {name}: {path}")

        pytest.fail("\n".join(error_msg))

    return True


@pytest.fixture(params=TEST_DATASETS.keys())
def dataset_name(request):
    """Parametrize tests across all datasets."""
    return request.param


@pytest.fixture
def dataset_info(dataset_name: str, all_test_datasets: Dict) -> Dict:
    """Get full dataset information for a given dataset name."""
    return all_test_datasets[dataset_name]


@pytest.fixture
def dataset_path(dataset_info: Dict) -> str:
    """Get the file path for the current dataset."""
    return dataset_info["path"]


@pytest.fixture
def loaded_session(dataset_path: str):
    """Load a dataset through dash_app to inspect dataset availability."""
    path = Path(dataset_path)
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode()
    contents = f"data:application/zip;base64,{encoded}"
    session = load_session_data_from_zip(contents, path.name)
    try:
        yield session
    finally:
        session.dispose()


@pytest.fixture
def page(page, base_url, dataset_path):
    """Enhanced page fixture that navigates to app and uploads a file.

    Deploy 20.21 Phase 3: 実際のブラウザアップロード方式に変更
    - API直接POST + goto ではコールバックチェーンが発火しないため
    - set_input_files を使用して実際のファイルアップロードを実行
    """
    # Navigate to the application
    page.goto(base_url)
    page.wait_for_load_state("networkidle")

    # Upload file via actual file input (not API)
    # This triggers the proper Dash callback chain
    path = Path(dataset_path)
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(str(path.absolute()))

    # Wait for upload processing and UI update
    # The callback chain: process_upload -> main-content -> tabs
    page.wait_for_timeout(5000)  # Initial processing time

    # Wait for tabs to appear (using actual element ID from dash_app.py)
    page.wait_for_selector('#overview-tab-container', timeout=30000)
    page.wait_for_timeout(2000)  # Additional wait for initial rendering

    return page


# ==============================================================================
# Filtered Dataset Fixtures
# ==============================================================================

@pytest.fixture(params=[k for k, v in TEST_DATASETS.items() if "multi-scenario" in v["tags"]])
def multi_scenario_dataset(request):
    """Only datasets with multiple scenarios."""
    return request.param


@pytest.fixture(params=[k for k, v in TEST_DATASETS.items() if "regional" in v["tags"]])
def regional_dataset(request):
    """Only regional datasets (Tennoh, Ashikaga)."""
    return request.param


@pytest.fixture(params=[k for k, v in TEST_DATASETS.items() if "production" in v["tags"]])
def production_dataset(request):
    """Only production datasets."""
    return request.param


# ==============================================================================
# Helper Functions
# ==============================================================================

def get_dataset_by_tag(tag: str) -> List[str]:
    """Get all dataset names matching a specific tag."""
    return [name for name, info in TEST_DATASETS.items() if tag in info["tags"]]


def get_largest_dataset() -> str:
    """Get the name of the largest dataset."""
    return max(TEST_DATASETS.items(), key=lambda x: x[1]["size_kb"])[0]


def get_smallest_dataset() -> str:
    """Get the name of the smallest dataset."""
    return min(TEST_DATASETS.items(), key=lambda x: x[1]["size_kb"])[0]


# ==============================================================================
# Pytest Configuration
# ==============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "multi_dataset: Tests that run across all datasets"
    )
    config.addinivalue_line(
        "markers", "regional: Tests specific to regional datasets"
    )
    config.addinivalue_line(
        "markers", "comparative: Tests comparing multiple datasets"
    )
    config.addinivalue_line(
        "markers", "data_quality: Tests validating data quality"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their names."""
    for item in items:
        # Auto-mark multi-dataset tests
        if "dataset_name" in item.fixturenames or "dataset_path" in item.fixturenames:
            item.add_marker(pytest.mark.multi_dataset)

        # Auto-mark comparative tests
        if "comparative" in item.name or "cross_dataset" in item.name:
            item.add_marker(pytest.mark.comparative)

        # Auto-mark data quality tests
        if "data_quality" in item.name or "validate" in item.name:
            item.add_marker(pytest.mark.data_quality)
