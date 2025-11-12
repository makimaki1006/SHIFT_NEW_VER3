"""
Phase 3.1でコメントアウトされた16個のコールバックを復活させるスクリプト

目的: Deploy 20.9で全タブが空白になる問題を解決
方法: 各コールバック関数のコメントアウトを解除
"""

import re

# 復活対象のコールバック関数名リスト
CALLBACKS_TO_RESTORE = [
    # 初期表示コールバック (16個)
    "initialize_overview_content",
    "initialize_heatmap_content",
    "initialize_shortage_content",
    "initialize_optimization_content",
    "initialize_leave_content",
    "initialize_cost_content",
    "initialize_hire_plan_content",
    "initialize_fatigue_content",
    "initialize_forecast_content",
    "initialize_fairness_content",
    "initialize_gap_content",
    "initialize_team_analysis_content",
    "initialize_blueprint_analysis_content",
    "initialize_logic_analysis_content",
    "initialize_individual_analysis_content",
    "initialize_ai_analysis_content",
    # 動的インタラクションコールバック (8個)
    "update_overview_insights",
    "update_shortage_insights",
    "update_hire_plan_insights",
    "update_optimization_insights",
    "update_leave_insights",
    "update_cost_insights",
    "update_individual_analysis_content",
    "update_team_analysis_graphs",
]

def restore_commented_callbacks(file_path):
    """コメントアウトされたコールバックを復活"""

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified_lines = []
    i = 0
    restored_count = 0

    while i < len(lines):
        line = lines[i]

        # コメントアウトヘッダーを検出
        if "# ===== COMMENTED OUT:" in line and "Phase 3.1:" in line:
            # どのコールバックか特定
            callback_name = None
            for name in CALLBACKS_TO_RESTORE:
                if name in line:
                    callback_name = name
                    break

            if callback_name:
                print(f"復活中: {callback_name} at line {i+1}")

                # ヘッダー行をスキップ
                i += 1

                # 次の行から関数定義が終わるまで、コメントアウトを解除
                while i < len(lines):
                    current_line = lines[i]

                    # 空のコメント行 "# " で終了
                    if current_line.strip() == "#":
                        i += 1
                        break

                    # 次のcallbackに到達したら終了
                    if current_line.strip().startswith("@app.callback") and not current_line.strip().startswith("#"):
                        break

                    # コメントアウトされた行を復活
                    if current_line.startswith("# "):
                        # "# " を削除
                        restored_line = current_line[2:]
                        modified_lines.append(restored_line)
                    elif current_line.startswith("#"):
                        # "#" のみを削除
                        restored_line = current_line[1:]
                        modified_lines.append(restored_line)
                    else:
                        # コメントでない行はそのまま
                        modified_lines.append(current_line)

                    i += 1

                restored_count += 1
                continue

        modified_lines.append(line)
        i += 1

    # ファイルに書き込み
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)

    print(f"\n✅ 完了: {restored_count}個のコールバックを復活しました")
    return restored_count

if __name__ == "__main__":
    file_path = "dash_app.py"
    restored_count = restore_commented_callbacks(file_path)

    if restored_count == len(CALLBACKS_TO_RESTORE):
        print(f"✅ 全{len(CALLBACKS_TO_RESTORE)}個のコールバックを正常に復活しました")
    else:
        print(f"⚠️ 警告: {len(CALLBACKS_TO_RESTORE)}個中{restored_count}個のみ復活")
