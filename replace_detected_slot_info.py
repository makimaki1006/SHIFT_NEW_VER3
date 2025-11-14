#!/usr/bin/env python3
"""
Deploy 20.17: DETECTED_SLOT_INFO参照を_get_current_slot_info()に置換

17箇所の使用箇所を修正:
- UI表示、time_labels生成などの参照を thread-local関数に置換
- SessionData初期化コードは保持（既に正しく動作している）
"""
import re

def main():
    # ファイル読み込み
    with open("dash_app.py", "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    # 置換パターン1: DETECTED_SLOT_INFO['slot_minutes'] → _get_current_slot_info()['slot_minutes']
    # ただし、SessionData初期化 (Line 1083) とingest_excel()更新 (Line 2027-2028) は保持

    # UI表示、time_labels生成の参照を置換
    replacements = [
        # generate_heatmap_figure() Line 3076
        ("slot_minutes = DETECTED_SLOT_INFO['slot_minutes']",
         "slot_minutes = _get_current_slot_info()['slot_minutes']  # Phase 1: Deploy 20.17"),

        # generate_heatmap_figure() Line 3200-3201 (confidence_info)
        ("if DETECTED_SLOT_INFO['auto_detected']:",
         "if _get_current_slot_info()['auto_detected']:  # Phase 1: Deploy 20.17"),
        ("confidence_info = f\" (検出スロット: {slot_minutes}分, 信頼度: {DETECTED_SLOT_INFO['confidence']:.2f})\"",
         "confidence_info = f\" (検出スロット: {slot_minutes}分, 信頼度: {_get_current_slot_info()['confidence']:.2f})\"  # Phase 1: Deploy 20.17"),

        # create_heatmap_tab() Line 3745, 3747
        ("f\"{DETECTED_SLOT_INFO['slot_minutes']}分スロット単位での真の過不足分析による職種別・雇用形態別算出\"",
         "f\"{_get_current_slot_info()['slot_minutes']}分スロット単位での真の過不足分析による職種別・雇用形態別算出\"  # Phase 1: Deploy 20.17"),
        ("f\"1スロット = {DETECTED_SLOT_INFO['slot_hours']:.2f}時間（{DETECTED_SLOT_INFO['slot_minutes']}分間隔）\"",
         "f\"1スロット = {_get_current_slot_info()['slot_hours']:.2f}時間（{_get_current_slot_info()['slot_minutes']}分間隔）\"  # Phase 1: Deploy 20.17"),

        # create_heatmap_tab() Line 3834
        ("time_labels = gen_labels(DETECTED_SLOT_INFO['slot_minutes'])",
         "time_labels = gen_labels(_get_current_slot_info()['slot_minutes'])  # Phase 1: Deploy 20.17"),

        # create_shortage_tab() Line 9267, 9314
        # 複数箇所あるため、全て置換
    ]

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"[OK] Replaced: {old[:50]}...")
        else:
            print(f"[WARN] Not found: {old[:50]}...")

    # create_shortage_tab()内のDETECTED_SLOT_INFO参照を置換（Line 9267, 9314など）
    # gen_labels(DETECTED_SLOT_INFO['slot_minutes'])パターン
    pattern_gen_labels = re.compile(r"gen_labels\(DETECTED_SLOT_INFO\['slot_minutes'\]\)")
    matches = pattern_gen_labels.findall(content)
    if matches:
        content = pattern_gen_labels.sub("gen_labels(_get_current_slot_info()['slot_minutes'])", content)
        print(f"[OK] Replaced {len(matches)} gen_labels() calls")

    # ingest_excel()のLine 2027-2028は保持（SessionDataが正しく動作しているため）
    # load_session_data_from_zip()のLine 1083も保持

    # バックアップ作成
    with open("dash_app.py.backup_before_detected_slot_info_replace_20171114", "w", encoding="utf-8") as f:
        f.write(original_content)

    print(f"\n[INFO] Backup created: dash_app.py.backup_before_detected_slot_info_replace_20171114")

    # 修正後のファイルを書き込み
    with open("dash_app.py", "w", encoding="utf-8") as f:
        f.write(content)

    # 修正箇所数をカウント
    diff_count = content.count("_get_current_slot_info()") - original_content.count("_get_current_slot_info()")
    print(f"\n[SUCCESS] Added {diff_count} _get_current_slot_info() calls")
    print(f"[INFO] dash_app.py updated")

if __name__ == "__main__":
    main()
