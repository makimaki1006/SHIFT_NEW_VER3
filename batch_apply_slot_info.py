#!/usr/bin/env python3
"""
Deploy 20.17: page_*()関数に slot_info 設定を一括追加

単純なテキスト置換で、page_heatmap()を除く17個の関数を修正
"""

def main():
    # ファイル読み込み
    with open("dash_app.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 修正対象の関数リスト（page_heatmap()は既に修正済み）
    functions = [
        "page_overview",
        "page_shortage",
        "page_individual",
        "page_team",
        "page_fatigue",
        "page_leave",
        "page_fairness",
        "page_optimization",
        "page_forecast",
        "page_hire_plan",
        "page_cost",
        "page_gap_analysis",
        "page_blueprint",
        "page_logic",
        "page_mind_reader",
        "page_summary",
        "page_reports"
    ]

    modified_count = 0

    for func in functions:
        # パターン1: old_session_idの後にold_slot_infoを追加
        old_pattern_1 = f"    old_session_id = _get_current_session_id()\n    _set_current_scenario_dir"
        new_pattern_1 = f"    old_session_id = _get_current_session_id()\n    old_slot_info = _get_current_slot_info()  # Phase 1: Deploy 20.17\n    _set_current_scenario_dir"

        # パターン2: _set_current_session_id(session_id)の後に_set_current_slot_infoを追加
        old_pattern_2 = f"    _set_current_session_id(session_id)\n    try:"
        new_pattern_2 = f"    _set_current_session_id(session_id)\n    _set_current_slot_info(session.slot_info)  # Phase 1: Deploy 20.17\n    try:"

        # パターン3: finallyブロックに_set_current_slot_infoを追加
        old_pattern_3 = f"        _set_current_session_id(old_session_id)\n\n\ndef {func}"
        new_pattern_3 = f"        _set_current_session_id(old_session_id)\n        _set_current_slot_info(old_slot_info)  # Phase 1: Deploy 20.17\n\n\ndef {func}"

        # 最後の関数の場合（page_reports）は次の関数がないので特別処理
        if func == "page_reports":
            old_pattern_3 = f"        _set_current_session_id(old_session_id)"
            # 次の行を読んで、関数定義でなければそのままにする
            # とりあえず、修正を諦めるか、ファイル末尾を確認
            # ここでは簡単のため、パターンを変更
            import re
            # page_reports のfinallyブロック直後まで探す
            pattern = re.compile(
                r"(def page_reports\(.*?\n.*?_set_current_session_id\(old_session_id\))\n",
                re.DOTALL
            )
            match = pattern.search(content)
            if match:
                before = match.group(1)
                after = content[match.end():]
                content = content[:match.start()] + before + "\n        _set_current_slot_info(old_slot_info)  # Phase 1: Deploy 20.17\n" + after
                modified_count += 1
                print(f"[OK] {func} modified (special case)")
            continue

        # 置換実行
        if old_pattern_1 in content:
            content = content.replace(old_pattern_1, new_pattern_1, 1)
            print(f"[OK] {func}: Added old_slot_info")
        else:
            print(f"[WARN] {func}: Pattern 1 not found")

        if old_pattern_2 in content:
            content = content.replace(old_pattern_2, new_pattern_2, 1)
            print(f"[OK] {func}: Added _set_current_slot_info(session.slot_info)")
        else:
            print(f"[WARN] {func}: Pattern 2 not found")

        if old_pattern_3 in content:
            content = content.replace(old_pattern_3, new_pattern_3, 1)
            modified_count += 1
            print(f"[OK] {func}: Added _set_current_slot_info(old_slot_info) in finally")
        else:
            print(f"[WARN] {func}: Pattern 3 not found")

    # 修正後のファイルを書き込み
    with open("dash_app.py", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n[SUCCESS] Modified {modified_count}/{len(functions)} functions")
    print(f"[INFO] dash_app.py updated")

if __name__ == "__main__":
    main()
