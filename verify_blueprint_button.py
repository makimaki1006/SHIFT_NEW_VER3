#!/usr/bin/env python3
"""
ブループリント分析ボタンの動作確認スクリプト

このスクリプトは以下を確認します:
1. サーバーが起動しているか
2. ブループリント分析タブが表示されるか
3. ボタンが存在するか
4. ボタンをクリックした際の挙動
"""

import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8055"
TEST_ZIP = "data/e2e-fixtures/analysis_7.zip"

def verify_blueprint_button():
    """ブループリント分析ボタンの動作確認"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # ブラウザを表示して確認
        page = browser.new_page()

        # コンソールログを監視
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

        # ページエラーを監視
        page_errors = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            print("=" * 80)
            print("ブループリント分析ボタン動作確認")
            print("=" * 80)

            # 1. ページアクセス
            print("\n[Step 1] ページアクセス...")
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 2. データアップロード
            print("\n[Step 2] テストデータアップロード...")
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(TEST_ZIP)
            print(f"  ✅ ファイルアップロード: {TEST_ZIP}")

            # データ処理完了を待つ
            print("\n[Step 3] データ処理完了を待機...")
            page.wait_for_selector('#overview-tab-container', timeout=30000)
            time.sleep(3)
            print("  ✅ データ処理完了")

            # 3. ブループリント分析タブに移動
            print("\n[Step 4] ブループリント分析タブに移動...")

            # タブのインデックスを確認
            tabs = page.locator('#main-tabs .tab').all()
            print(f"  タブ数: {len(tabs)}")

            # ブループリントタブは13番目（index 13）
            blueprint_tab_index = 13

            # dash_clientside.set_propsを使用してタブ切り替え
            js_code = f"""
            if (window.dash_clientside && window.dash_clientside.set_props) {{
                window.dash_clientside.set_props('main-tabs', {{value: 'blueprint_analysis'}});
                console.log('[Test] Tab switched to blueprint_analysis');
            }} else {{
                console.log('[Test] dash_clientside.set_props not available');
            }}
            """
            page.evaluate(js_code)
            time.sleep(2)

            # タブコンテナが表示されているか確認
            blueprint_container = page.locator('#blueprint-analysis-tab-container')
            is_visible = blueprint_container.is_visible()
            print(f"  ブループリント分析コンテナ表示: {is_visible}")

            if not is_visible:
                print("  ❌ ブループリント分析タブが表示されていません")
                # スクリーンショット撮影
                page.screenshot(path="reports/blueprint_tab_not_visible.png")
                print("  📸 スクリーンショット保存: reports/blueprint_tab_not_visible.png")
                return False

            print("  ✅ ブループリント分析タブが表示されました")

            # 4. ボタンの存在確認
            print("\n[Step 5] 「ブループリントを生成」ボタンの確認...")
            button = page.locator('#generate-blueprint-button')

            if not button.count():
                print("  ❌ ボタンが見つかりません")
                page.screenshot(path="reports/blueprint_button_not_found.png")
                return False

            print("  ✅ ボタンが見つかりました")
            print(f"  ボタンテキスト: {button.text_content()}")
            print(f"  ボタンが有効: {button.is_enabled()}")
            print(f"  ボタンが表示: {button.is_visible()}")

            # 5. ボタンクリック前のスクリーンショット
            page.screenshot(path="reports/blueprint_before_click.png")
            print("\n  📸 クリック前スクリーンショット: reports/blueprint_before_click.png")

            # 6. ボタンクリック
            print("\n[Step 6] ボタンをクリック...")
            button.click()
            print("  ✅ ボタンクリック実行")

            # 結果を待つ
            time.sleep(5)

            # 7. クリック後のスクリーンショット
            page.screenshot(path="reports/blueprint_after_click.png")
            print("\n  📸 クリック後スクリーンショット: reports/blueprint_after_click.png")

            # 8. コンソールログ確認
            print("\n[Step 7] コンソールログ確認...")
            if console_messages:
                print(f"  コンソールメッセージ数: {len(console_messages)}")
                for msg in console_messages[-20:]:  # 最新20件
                    print(f"    {msg}")
            else:
                print("  コンソールメッセージなし")

            # 9. ページエラー確認
            print("\n[Step 8] ページエラー確認...")
            if page_errors:
                print(f"  ❌ エラー数: {len(page_errors)}")
                for err in page_errors:
                    print(f"    {err}")
            else:
                print("  ✅ ページエラーなし")

            # 10. 結果確認
            print("\n[Step 9] 分析結果の確認...")

            # 結果要素が表示されているか確認（Deploy 20.27: 新ID対応）
            result_elements = {
                'tradeoff-scatter-plot': page.locator('#tradeoff-scatter-plot').count() > 0,
                'rules-data-table': page.locator('#rules-data-table').count() > 0,
                'blueprint-facts-table': page.locator('#blueprint-facts-table').count() > 0,
                'blueprint-facts-summary': page.locator('#blueprint-facts-summary').count() > 0,
                'blueprint-integrated-content': page.locator('#blueprint-integrated-content').count() > 0,
            }

            print("  結果要素の存在:")
            for element_id, exists in result_elements.items():
                status = "✅" if exists else "❌"
                print(f"    {status} {element_id}: {exists}")

            # 11. 総合判定
            print("\n" + "=" * 80)
            print("総合結果")
            print("=" * 80)

            all_elements_exist = all(result_elements.values())

            if all_elements_exist:
                print("✅ ブループリント分析ボタンは正常に動作しています")
                return True
            else:
                print("❌ ブループリント分析ボタンに問題があります")
                print("\n問題の詳細:")
                for element_id, exists in result_elements.items():
                    if not exists:
                        print(f"  - {element_id} が表示されていません")
                return False

        except Exception as e:
            print(f"\n❌ エラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()
            page.screenshot(path="reports/blueprint_error.png")
            print("📸 エラー時スクリーンショット: reports/blueprint_error.png")
            return False

        finally:
            # ブラウザを10秒間開いたままにして目視確認できるようにする
            print("\n[最終確認] ブラウザを10秒間開いたままにします...")
            time.sleep(10)
            browser.close()

if __name__ == "__main__":
    success = verify_blueprint_button()
    exit(0 if success else 1)
