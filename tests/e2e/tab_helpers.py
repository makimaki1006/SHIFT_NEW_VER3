"""Tab navigation helpers for E2E tests.

Phase 4: タブ切替のためのヘルパーユーティリティ
"""
from playwright.sync_api import Page

# Tab index to name mapping
TAB_MAP = {
    'overview': 0,
    'heatmap': 1,
    'shortage': 2,
    'individual': 3,
    'team': 4,
    'fatigue': 5,
    'leave': 6,
    'fairness': 7,
    'optimization': 8,
    'forecast': 9,
    'hire-plan': 10,
    'cost': 11,
    'gap': 12,
    'blueprint': 13,
    'logic': 14,
}

# Tab container ID mapping
TAB_CONTAINER_MAP = {
    'overview': 'overview-tab-container',
    'heatmap': 'heatmap-tab-container',
    'shortage': 'shortage-tab-container',
    'individual': 'individual-analysis-tab-container',
    'team': 'team-analysis-tab-container',
    'fatigue': 'fatigue-tab-container',
    'leave': 'leave-tab-container',
    'fairness': 'fairness-tab-container',
    'optimization': 'optimization-tab-container',
    'forecast': 'forecast-tab-container',
    'hire-plan': 'hire-plan-tab-container',
    'cost': 'cost-tab-container',
    'gap': 'gap-tab-container',
    'blueprint': 'blueprint-analysis-tab-container',
    'logic': 'logic-analysis-tab-container',
}


def click_tab(page: Page, tab_name: str, timeout: int = 30000) -> None:
    """Click a tab by name and wait for its container to be visible.

    Args:
        page: Playwright page object
        tab_name: Tab name (e.g., 'heatmap', 'shortage')
        timeout: Timeout in milliseconds for waiting

    Raises:
        ValueError: If tab_name is not recognized
        TimeoutError: If tab container doesn't become visible
    """
    if tab_name not in TAB_MAP:
        raise ValueError(f"Unknown tab: {tab_name}. Available: {list(TAB_MAP.keys())}")

    tab_index = TAB_MAP[tab_name]
    container_id = TAB_CONTAINER_MAP[tab_name]

    # Get the tab value name for Dash
    tab_values = ['overview', 'heatmap', 'shortage', 'individual', 'team',
                  'fatigue', 'leave', 'fairness', 'optimization', 'forecast',
                  'hire-plan', 'cost', 'gap', 'blueprint', 'logic']
    tab_value = tab_values[tab_index]

    # Click the tab using the tab value selector
    # dcc.Tabs uses div[data-value] for tab selection
    selector = f'#main-tabs > div.tab:nth-child({tab_index + 1})'

    # Try clicking the tab element
    page.click(selector)

    # Wait for callback to process
    page.wait_for_timeout(3000)

    # Wait for the tab container to become visible
    # Note: Some tabs may take longer to render content
    try:
        page.wait_for_selector(f'#{container_id}', state='visible', timeout=timeout)
    except Exception:
        # If timeout, check if element exists but is hidden (style issue)
        element = page.locator(f'#{container_id}')
        if element.count() > 0:
            # Element exists, wait a bit more for style change
            page.wait_for_timeout(3000)
            if not element.is_visible():
                raise TimeoutError(f'Tab container {container_id} exists but not visible after click')
        else:
            raise

    # Additional wait for content rendering
    page.wait_for_timeout(1000)


def get_current_tab(page: Page) -> str:
    """Get the currently selected tab name.

    Returns:
        Tab name (e.g., 'overview', 'heatmap')
    """
    selected = page.locator('#main-tabs > div.tab.tab--selected').first
    text = selected.inner_text()

    # Map text to tab name
    text_to_tab = {
        '概要': 'overview',
        'ヒートマップ': 'heatmap',
        '不足分析': 'shortage',
        '職員個別分析': 'individual',
        'チーム分析': 'team',
        '疲労分析': 'fatigue',
        '休暇分析': 'leave',
        '公平性': 'fairness',
        '最適化分析': 'optimization',
        '需要予測': 'forecast',
        '採用計画': 'hire-plan',
        'コスト分析': 'cost',
        '基準乖離分析': 'gap',
        '作成ブループリント': 'blueprint',
        'ロジック解明': 'logic',
    }

    for jp_text, tab_name in text_to_tab.items():
        if jp_text in text:
            return tab_name

    return 'unknown'


def wait_for_tab_content(page: Page, tab_name: str, timeout: int = 30000) -> None:
    """Wait for tab content to be loaded (container visible).

    Args:
        page: Playwright page object
        tab_name: Tab name
        timeout: Timeout in milliseconds
    """
    if tab_name not in TAB_CONTAINER_MAP:
        raise ValueError(f"Unknown tab: {tab_name}")

    container_id = TAB_CONTAINER_MAP[tab_name]
    page.wait_for_selector(f'#{container_id}', state='visible', timeout=timeout)


def is_tab_visible(page: Page, tab_name: str) -> bool:
    """Check if a tab's content container is visible.

    Args:
        page: Playwright page object
        tab_name: Tab name

    Returns:
        True if the tab container is visible
    """
    if tab_name not in TAB_CONTAINER_MAP:
        return False

    container_id = TAB_CONTAINER_MAP[tab_name]
    return page.locator(f'#{container_id}').is_visible()
