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

    Uses value direct update method to ensure main-tabs.value is properly updated,
    which triggers the Dash callback chain.

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

    # Get the tab value name for Dash (must match app's main-tabs value definitions)
    # Correct values from dash_app.py:8365 and update_tab_visibility
    tab_values = ['overview', 'heatmap', 'shortage', 'individual_analysis', 'team_analysis',
                  'fatigue', 'leave', 'fairness', 'optimization', 'forecast',
                  'hire_plan', 'cost', 'gap', 'blueprint_analysis', 'logic_analysis']
    tab_value = tab_values[tab_index]

    # Method A: Use dash_clientside.set_props to directly update main-tabs.value
    # This ensures the Dash callback chain is triggered properly
    js_code = """() => {
        try {
            // Try dash_clientside.set_props first (most reliable for Dash)
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props('main-tabs', {value: '%s'});
                return {success: true, method: 'set_props'};
            }

            // Fallback: DOM click
            const selector = '#main-tabs > div.tab:nth-child(%d)';
            const tabEl = document.querySelector(selector);
            if (tabEl) {
                tabEl.click();
                return {success: true, method: 'dom_click'};
            }

            return {success: false, error: 'No method worked'};
        } catch (err) {
            return {success: false, error: err.message};
        }
    }""" % (tab_value, tab_index + 1)

    result = page.evaluate(js_code)

    if not result.get('success'):
        raise RuntimeError(f"Failed to switch tab: {result.get('error', 'Unknown error')}")

    # Wait for callback to process
    page.wait_for_timeout(3000)

    # Wait for the tab container to become visible
    # Note: Use style.display check instead of Playwright's wait_for_selector
    # because is_visible() may return False even when display='block'
    import time
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        display = page.evaluate(f"""() => {{
            const el = document.getElementById('{container_id}');
            return el ? el.style.display : 'none';
        }}""")
        if display != 'none' and display != '':
            break
        page.wait_for_timeout(500)
    else:
        # Check if element exists
        exists = page.evaluate(f"""() => {{
            return document.getElementById('{container_id}') !== null;
        }}""")
        if exists:
            raise TimeoutError(f'Tab container {container_id} exists but style.display is still hidden after click')
        else:
            raise TimeoutError(f'Tab container {container_id} not found')

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
        True if the tab container is visible (display != 'none')
    """
    if tab_name not in TAB_CONTAINER_MAP:
        return False

    container_id = TAB_CONTAINER_MAP[tab_name]

    # Check style.display instead of Playwright's is_visible()
    # because is_visible() may return False even when display='block'
    # if the element is not in viewport
    display = page.evaluate(f"""() => {{
        const el = document.getElementById('{container_id}');
        return el ? el.style.display : 'none';
    }}""")

    return display != 'none' and display != ''
