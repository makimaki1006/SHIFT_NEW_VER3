from pathlib import Path
import json
import time
from playwright.sync_api import sync_playwright

BASE_URL = 'http://127.0.0.1:8055'

DATASETS = {
    'analysis_7': 'data/e2e-fixtures/analysis_7.zip',
    'analysis_8': 'data/e2e-fixtures/analysis_8.zip',
    'analysis_9': 'data/e2e-fixtures/analysis_9.zip',
    'tennoh_august': 'data/e2e-fixtures/tennoh_august.zip',
    'ashikaga_august': 'data/e2e-fixtures/ashikaga_august.zip',
}

TAB_KEYS = [
    'overview','heatmap','shortage','individual','team',
    'fatigue','leave','fairness','optimization','forecast',
    'hire-plan','cost','gap','blueprint','logic','ai',
]

TAB_INDEX = {
    'overview':0,'heatmap':1,'shortage':2,'individual':3,'team':4,
    'fatigue':5,'leave':6,'fairness':7,'optimization':8,'forecast':9,
    'hire-plan':10,'cost':11,'gap':12,'blueprint':13,'logic':14,'ai':15,
}

TAB_CONTAINER = {
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
    'ai': 'ai-analysis-tab-container',
}

CONTENT_SELECTORS = ['.js-plotly-plot','.plotly','.dash-table','table','svg','canvas','.card','img']

# Mapping from tab key to correct Dash tab value (must match app's main-tabs value definitions)
# Correct values from dash_app.py:8365 and update_tab_visibility
TAB_VALUE_MAP = {
    'overview': 'overview',
    'heatmap': 'heatmap',
    'shortage': 'shortage',
    'individual': 'individual_analysis',
    'team': 'team_analysis',
    'fatigue': 'fatigue',
    'leave': 'leave',
    'fairness': 'fairness',
    'optimization': 'optimization',
    'forecast': 'forecast',
    'hire-plan': 'hire_plan',
    'cost': 'cost',
    'gap': 'gap',
    'blueprint': 'blueprint_analysis',
    'logic': 'logic_analysis',
    'ai': 'ai_analysis',
}

def click_tab_local(page, key: str):
    """Click tab using value direct update method.

    Uses dash_clientside.set_props to directly update main-tabs.value,
    which properly triggers the Dash callback chain.
    """
    idx = TAB_INDEX.get(key, 0)
    tab_value = TAB_VALUE_MAP.get(key, key)  # Use correct value mapping

    # Use dash_clientside.set_props to directly update main-tabs.value
    js_code = """(() => {
        try {
            // Method A: dash_clientside.set_props (most reliable)
            if (window.dash_clientside && window.dash_clientside.set_props) {
                window.dash_clientside.set_props('main-tabs', {value: '%s'});
                return {success: true, method: 'set_props'};
            }

            // Fallback: DOM click
            const tabs = document.querySelectorAll('#main-tabs .tab');
            const el = tabs[%d];
            if (el) {
                el.click();
                return {success: true, method: 'dom_click'};
            }

            return {success: false, error: 'No method worked'};
        } catch (err) {
            return {success: false, error: err.message};
        }
    })()""" % (tab_value, idx)

    result = page.evaluate(js_code)

    # Wait for callback to process
    time.sleep(1)

def is_visible_local(page, container_id: str) -> bool:
    return bool(page.evaluate(f"(() => {{ const el = document.getElementById('{container_id}'); if (!el) return false; const cs = window.getComputedStyle(el); return cs && cs.display !== 'none'; }})()"))

def run_for_dataset(page, dataset_path: Path):
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    page.locator('input[type="file"]').set_input_files(str(dataset_path.absolute()))
    page.wait_for_selector('#overview-tab-container', timeout=30000)
    time.sleep(1)

    results = {}
    for key in TAB_KEYS:
        entry = {'clicked': False,'visible': False,'content_type': 'none','screenshot': f'reports/e2e_playwright/artifacts/screenshots/tab_{key}.png'}
        try:
            click_tab_local(page, key)
            entry['clicked'] = True
        except Exception:
            pass
        container_id = TAB_CONTAINER.get(key, '')
        try:
            entry['visible'] = is_visible_local(page, container_id) if container_id else False
        except Exception:
            entry['visible'] = False
        if container_id:
            for sel in CONTENT_SELECTORS:
                try:
                    if page.locator(f'#{container_id} {sel}').count() > 0:
                        entry['content_type'] = sel
                        break
                except Exception:
                    pass
        try:
            Path('reports/e2e_playwright/artifacts/screenshots').mkdir(parents=True, exist_ok=True)
            page.screenshot(path=entry['screenshot'])
        except Exception:
            pass
        results[key] = entry
    return results

def main():
    summary = {'datasets':{}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, path in DATASETS.items():
            dp = Path(path)
            if not dp.exists():
                summary['datasets'][name] = {'error': f'Missing dataset: {path}'}
                continue
            page = browser.new_page()
            errors, dups = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: dups.append(m.text) if 'Duplicate callback outputs' in m.text else None)
            res = run_for_dataset(page, dp)
            page.close()
            summary['datasets'][name] = {'pageerrors': len(errors), 'duplicate_msgs': len(dups), 'tabs': res}
        browser.close()
    Path('phase4_full_tabs_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote phase4_full_tabs_summary.json')

if __name__ == '__main__':
    main()
