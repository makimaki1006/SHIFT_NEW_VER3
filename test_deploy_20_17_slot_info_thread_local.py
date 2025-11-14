#!/usr/bin/env python3
"""
Deploy 20.17: thread-local slot_info動作確認テスト

目的:
- _get_current_slot_info()/_set_current_slot_info()の動作確認
- デフォルト値の確認
- カスタム値の設定/取得確認
"""
import sys
from dash_app import _set_current_slot_info, _get_current_slot_info

def test_slot_info_thread_local():
    """thread-local slot_info関数の動作確認"""

    print("=" * 80)
    print("Deploy 20.17: thread-local slot_info動作確認テスト")
    print("=" * 80)
    print()

    # ========================================================================
    # Test 1: デフォルト値確認
    # ========================================================================
    print("--- Test 1: デフォルト値確認 ---")

    default_info = _get_current_slot_info()

    if default_info['slot_minutes'] == 30:
        print(f"[OK] slot_minutes = {default_info['slot_minutes']} (デフォルト)")
    else:
        print(f"[NG] slot_minutes = {default_info['slot_minutes']} (期待値: 30)")
        return False

    if default_info['slot_hours'] == 0.5:
        print(f"[OK] slot_hours = {default_info['slot_hours']} (デフォルト)")
    else:
        print(f"[NG] slot_hours = {default_info['slot_hours']} (期待値: 0.5)")
        return False

    if default_info['auto_detected'] == False:
        print(f"[OK] auto_detected = {default_info['auto_detected']} (デフォルト)")
    else:
        print(f"[NG] auto_detected = {default_info['auto_detected']} (期待値: False)")
        return False

    print()

    # ========================================================================
    # Test 2: カスタム値設定 (15分スロット)
    # ========================================================================
    print("--- Test 2: カスタム値設定 (15分スロット) ---")

    custom_info_15 = {
        'slot_minutes': 15,
        'slot_hours': 0.25,
        'confidence': 0.95,
        'auto_detected': True
    }

    _set_current_slot_info(custom_info_15)

    retrieved = _get_current_slot_info()

    if retrieved['slot_minutes'] == 15:
        print(f"[OK] slot_minutes = {retrieved['slot_minutes']}")
    else:
        print(f"[NG] slot_minutes = {retrieved['slot_minutes']} (期待値: 15)")
        return False

    if retrieved['slot_hours'] == 0.25:
        print(f"[OK] slot_hours = {retrieved['slot_hours']}")
    else:
        print(f"[NG] slot_hours = {retrieved['slot_hours']} (期待値: 0.25)")
        return False

    if retrieved['confidence'] == 0.95:
        print(f"[OK] confidence = {retrieved['confidence']}")
    else:
        print(f"[NG] confidence = {retrieved['confidence']} (期待値: 0.95)")
        return False

    if retrieved['auto_detected'] == True:
        print(f"[OK] auto_detected = {retrieved['auto_detected']}")
    else:
        print(f"[NG] auto_detected = {retrieved['auto_detected']} (期待値: True)")
        return False

    print()

    # ========================================================================
    # Test 3: 異なるカスタム値に上書き (20分スロット)
    # ========================================================================
    print("--- Test 3: 異なる値に上書き (20分スロット) ---")

    custom_info_20 = {
        'slot_minutes': 20,
        'slot_hours': 0.333,
        'confidence': 0.88,
        'auto_detected': False
    }

    _set_current_slot_info(custom_info_20)

    retrieved_20 = _get_current_slot_info()

    if retrieved_20['slot_minutes'] == 20:
        print(f"[OK] slot_minutes = {retrieved_20['slot_minutes']} (上書き成功)")
    else:
        print(f"[NG] slot_minutes = {retrieved_20['slot_minutes']} (期待値: 20)")
        return False

    if retrieved_20['auto_detected'] == False:
        print(f"[OK] auto_detected = {retrieved_20['auto_detected']} (上書き成功)")
    else:
        print(f"[NG] auto_detected = {retrieved_20['auto_detected']} (期待値: False)")
        return False

    print()

    # ========================================================================
    # Test 4: None値の処理（デフォルトにフォールバック）
    # ========================================================================
    print("--- Test 4: None値の処理 ---")

    _set_current_slot_info(None)

    fallback_info = _get_current_slot_info()

    if fallback_info['slot_minutes'] == 30:
        print(f"[OK] Noneでデフォルトにフォールバック: slot_minutes = {fallback_info['slot_minutes']}")
    else:
        print(f"[NG] slot_minutes = {fallback_info['slot_minutes']} (期待値: 30)")
        return False

    print()

    # ========================================================================
    # 成功
    # ========================================================================
    print("=" * 80)
    print("[OK] Deploy 20.17: thread-local slot_info動作確認テスト - 全テスト合格")
    print("=" * 80)
    print()
    print("確認項目:")
    print("  [OK] デフォルト値が正しく返される")
    print("  [OK] カスタム値の設定が正常動作")
    print("  [OK] 値の上書きが正常動作")
    print("  [OK] None値で安全にデフォルトにフォールバック")
    print()

    return True

if __name__ == "__main__":
    success = test_slot_info_thread_local()
    sys.exit(0 if success else 1)
