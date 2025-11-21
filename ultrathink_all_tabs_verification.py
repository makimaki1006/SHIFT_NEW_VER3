"""Ultrathink 10-cycle verification for all 15 tabs

10 check items per tab:
1. Dependency - tab switching callback fires
2. Guard - container style.display changes
3. Visibility - container becomes visible
4. Content - tab-specific content exists
5. JS errors - no console errors
6. Duplicate - no duplicate callback warnings
7. DOM - expected DOM structure
8. Data consistency - data matches expectations
9. Latency - response time acceptable
10. Side effects - no unintended changes
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
import json
import time
import re

sys.path.insert(0, 'tests/e2e')
from tab_helpers import click_tab, get_current_tab, is_tab_visible, TAB_MAP, TAB_CONTAINER_MAP

ALL_TABS = list(TAB_MAP.keys())

def verify_all_tabs():
    results = {
        'summary': {'total': 0, 'passed': 0, 'failed': 0},
        'tabs': {},
        'console_errors': [],
        'duplicate_warnings': []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture console messages
        console_messages = []
        def handle_console(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text[:200]
            })
        page.on('console', handle_console)

        # Navigate and upload
        print("1. Navigate to app...")
        page.goto('http://127.0.0.1:8055')
        page.wait_for_load_state('networkidle')

        print("2. Upload test file...")
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(Path('data/e2e-fixtures/analysis_7.zip').absolute()))
        page.wait_for_timeout(8000)

        # Verify initial state
        initial_tab = get_current_tab(page)
        print(f"3. Initial tab: {initial_tab}")

        if initial_tab != 'overview':
            results['summary']['failed'] += 1
            print(f"   ERROR: Expected overview, got {initial_tab}")

        # Test each tab
        print("\n4. Testing all 15 tabs...\n")

        for tab_name in ALL_TABS:
            results['summary']['total'] += 1
            tab_result = {
                'checks': {},
                'passed': True,
                'errors': []
            }

            print(f"--- Tab: {tab_name} ---")

            try:
                # Clear console for this tab
                start_console_count = len(console_messages)
                start_time = time.time()

                # Check 1: Dependency - click tab
                try:
                    if tab_name != 'overview':  # Skip click for overview (already selected)
                        click_tab(page, tab_name)
                    tab_result['checks']['1_dependency'] = 'PASS'
                except Exception as e:
                    tab_result['checks']['1_dependency'] = f'FAIL: {str(e)[:50]}'
                    tab_result['passed'] = False
                    tab_result['errors'].append(str(e))

                # Check 2: Guard - container style
                container_id = TAB_CONTAINER_MAP[tab_name]
                display = page.evaluate(f"""() => {{
                    const el = document.getElementById('{container_id}');
                    return el ? el.style.display : 'NOT FOUND';
                }}""")
                if display == 'block':
                    tab_result['checks']['2_guard'] = 'PASS'
                else:
                    tab_result['checks']['2_guard'] = f'FAIL: display={display}'
                    tab_result['passed'] = False

                # Check 3: Visibility
                visible = is_tab_visible(page, tab_name)
                if visible:
                    tab_result['checks']['3_visibility'] = 'PASS'
                else:
                    tab_result['checks']['3_visibility'] = 'FAIL: not visible'
                    tab_result['passed'] = False

                # Check 4: Content - check for tab-specific content
                content_check = page.evaluate(f"""() => {{
                    const container = document.getElementById('{container_id}');
                    if (!container) return {{exists: false}};
                    return {{
                        exists: true,
                        childCount: container.children.length,
                        hasContent: container.innerHTML.length > 100
                    }};
                }}""")
                if content_check.get('hasContent'):
                    tab_result['checks']['4_content'] = 'PASS'
                else:
                    tab_result['checks']['4_content'] = f'FAIL: childCount={content_check.get("childCount", 0)}'
                    tab_result['passed'] = False

                # Check 5: JS errors
                new_errors = [m for m in console_messages[start_console_count:] if m['type'] == 'error']
                if not new_errors:
                    tab_result['checks']['5_js_errors'] = 'PASS'
                else:
                    tab_result['checks']['5_js_errors'] = f'FAIL: {len(new_errors)} errors'
                    tab_result['passed'] = False
                    for err in new_errors:
                        results['console_errors'].append(f"{tab_name}: {err['text']}")

                # Check 6: Duplicate callbacks
                duplicates = [m for m in console_messages[start_console_count:]
                             if 'duplicate' in m['text'].lower()]
                if not duplicates:
                    tab_result['checks']['6_duplicate'] = 'PASS'
                else:
                    tab_result['checks']['6_duplicate'] = f'FAIL: {len(duplicates)} duplicates'
                    tab_result['passed'] = False
                    for dup in duplicates:
                        results['duplicate_warnings'].append(f"{tab_name}: {dup['text']}")

                # Check 7: DOM structure
                dom_check = page.evaluate(f"""() => {{
                    const container = document.getElementById('{container_id}');
                    if (!container) return {{valid: false}};
                    // Check for common elements
                    const hasDiv = container.querySelector('div') !== null;
                    const hasText = container.innerText.length > 10;
                    return {{valid: hasDiv || hasText, hasDiv, hasText}};
                }}""")
                if dom_check.get('valid'):
                    tab_result['checks']['7_dom'] = 'PASS'
                else:
                    tab_result['checks']['7_dom'] = 'FAIL: invalid DOM'
                    tab_result['passed'] = False

                # Check 8: Data consistency (non-zero or N/A check)
                content_text = page.evaluate(f"() => (document.getElementById('{container_id}')?.innerText || '')")
                if re.search(r'\bN/A\b', content_text, re.IGNORECASE):
                    tab_result['checks']['8_data'] = 'PASS (N/A found)'
                else:
                    numbers = re.findall(r'\d+(?:\.\d+)?', content_text)
                    non_zero_found = any(float(n) > 0 for n in numbers if n)
                    if non_zero_found:
                        tab_result['checks']['8_data'] = 'PASS (non-zero data)'
                    else:
                        tab_result['checks']['8_data'] = 'FAIL: no non-zero data or N/A'
                        tab_result['passed'] = False

                # Check 9: Latency
                elapsed = time.time() - start_time
                if elapsed < 10:  # 10 second threshold
                    tab_result['checks']['9_latency'] = f'PASS ({elapsed:.1f}s)'
                else:
                    tab_result['checks']['9_latency'] = f'WARN: {elapsed:.1f}s'

                # Check 10: Side effects - check other tabs aren't affected
                other_visible = []
                for other_tab in ALL_TABS:
                    if other_tab != tab_name and is_tab_visible(page, other_tab):
                        other_visible.append(other_tab)
                if not other_visible:
                    tab_result['checks']['10_side_effects'] = 'PASS'
                else:
                    tab_result['checks']['10_side_effects'] = f'FAIL: {other_visible} also visible'
                    tab_result['passed'] = False

                # Summary for this tab
                if tab_result['passed']:
                    results['summary']['passed'] += 1
                    status = 'PASS'
                else:
                    results['summary']['failed'] += 1
                    status = 'FAIL'

                print(f"  Status: {status}")
                for check, result in tab_result['checks'].items():
                    print(f"    {check}: {result}")

            except Exception as e:
                tab_result['passed'] = False
                tab_result['errors'].append(str(e))
                results['summary']['failed'] += 1
                print(f"  ERROR: {str(e)[:100]}")

            results['tabs'][tab_name] = tab_result
            print()

        browser.close()

    return results

def run_ultrathink_cycles(num_cycles=10):
    """Run multiple verification cycles"""
    all_results = []

    for cycle in range(1, num_cycles + 1):
        print("=" * 60)
        print(f"ULTRATHINK CYCLE {cycle}/{num_cycles}")
        print("=" * 60)

        results = verify_all_tabs()
        all_results.append(results)

        # Print cycle summary
        print("\n" + "=" * 60)
        print(f"CYCLE {cycle} SUMMARY")
        print("=" * 60)
        print(f"Total: {results['summary']['total']}")
        print(f"Passed: {results['summary']['passed']}")
        print(f"Failed: {results['summary']['failed']}")

        if results['console_errors']:
            print(f"\nConsole Errors ({len(results['console_errors'])}):")
            for err in results['console_errors'][:5]:
                print(f"  - {err[:100]}")

        if results['duplicate_warnings']:
            print(f"\nDuplicate Warnings ({len(results['duplicate_warnings'])}):")
            for warn in results['duplicate_warnings'][:5]:
                print(f"  - {warn[:100]}")

        # List failed tabs
        failed_tabs = [tab for tab, data in results['tabs'].items() if not data['passed']]
        if failed_tabs:
            print(f"\nFailed Tabs: {', '.join(failed_tabs)}")
        else:
            print("\nAll tabs passed!")

        print("\n")

    # Final summary across all cycles
    print("=" * 60)
    print("FINAL ULTRATHINK SUMMARY")
    print("=" * 60)

    # Aggregate results
    tab_pass_counts = {tab: 0 for tab in ALL_TABS}
    total_errors = 0
    total_duplicates = 0

    for cycle_result in all_results:
        total_errors += len(cycle_result['console_errors'])
        total_duplicates += len(cycle_result['duplicate_warnings'])
        for tab, data in cycle_result['tabs'].items():
            if data['passed']:
                tab_pass_counts[tab] += 1

    print(f"\nTab Pass Rates ({num_cycles} cycles):")
    for tab in ALL_TABS:
        rate = tab_pass_counts[tab] / num_cycles * 100
        status = 'OK' if rate == 100 else 'WARN' if rate >= 80 else 'FAIL'
        print(f"  {tab}: {tab_pass_counts[tab]}/{num_cycles} ({rate:.0f}%) [{status}]")

    print(f"\nTotal Console Errors: {total_errors}")
    print(f"Total Duplicate Warnings: {total_duplicates}")

    # Overall verdict
    all_perfect = all(count == num_cycles for count in tab_pass_counts.values())
    if all_perfect and total_errors == 0 and total_duplicates == 0:
        print("\n*** VERDICT: ALL CHECKS PASSED ***")
    else:
        print("\n*** VERDICT: ISSUES DETECTED - REVIEW REQUIRED ***")

    # Save results
    with open('ultrathink_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'cycles': num_cycles,
            'tab_pass_counts': tab_pass_counts,
            'total_errors': total_errors,
            'total_duplicates': total_duplicates,
            'all_results': all_results
        }, f, indent=2, ensure_ascii=False, default=str)
    print("\nResults saved to ultrathink_results.json")

if __name__ == '__main__':
    run_ultrathink_cycles(10)
