"""
Deploy 20.17: マルチセッションでのslot_info分離テスト

目的: 複数のセッションが異なるslot_infoを保持できることを検証

テストシナリオ:
1. セッションA: 15分スロット（病院A）
2. セッションB: 30分スロット（病院B）
3. セッションC: 20分スロット（病院C）
4. 各セッションのslot_infoが混入しないことを確認
"""

import sys
from pathlib import Path
import threading
import time

# dash_appをインポート
sys.path.insert(0, str(Path(__file__).parent))
import dash_app
from dash_app import (
    _get_current_slot_info,
    _set_current_slot_info,
    SessionData,
    register_session,
    get_session
)


def test_multi_session_slot_info_isolation():
    """マルチセッションでのslot_info分離テスト"""

    print("=" * 80)
    print("Deploy 20.17: マルチセッションslot_info分離テスト")
    print("=" * 80)

    # テスト結果を格納
    results = {
        'session_a': None,
        'session_b': None,
        'session_c': None,
        'errors': []
    }

    def session_a_worker():
        """セッションA: 15分スロット（病院A）"""
        try:
            # 病院Aのslot_infoを設定
            slot_info_a = {
                'slot_minutes': 15,
                'slot_hours': 0.25,
                'confidence': 0.95,
                'auto_detected': True
            }
            _set_current_slot_info(slot_info_a)

            # わずかに待機（他のスレッドと競合させる）
            time.sleep(0.01)

            # slot_infoを取得
            retrieved = _get_current_slot_info()
            results['session_a'] = retrieved

            # 検証
            assert retrieved['slot_minutes'] == 15, f"Expected 15, got {retrieved['slot_minutes']}"
            assert retrieved['confidence'] == 0.95, f"Expected 0.95, got {retrieved['confidence']}"

        except Exception as e:
            results['errors'].append(f"Session A error: {e}")

    def session_b_worker():
        """セッションB: 30分スロット（病院B）"""
        try:
            # 病院Bのslot_infoを設定（デフォルト）
            slot_info_b = {
                'slot_minutes': 30,
                'slot_hours': 0.5,
                'confidence': 1.0,
                'auto_detected': False
            }
            _set_current_slot_info(slot_info_b)

            # わずかに待機
            time.sleep(0.02)

            # slot_infoを取得
            retrieved = _get_current_slot_info()
            results['session_b'] = retrieved

            # 検証
            assert retrieved['slot_minutes'] == 30, f"Expected 30, got {retrieved['slot_minutes']}"
            assert retrieved['auto_detected'] == False, f"Expected False, got {retrieved['auto_detected']}"

        except Exception as e:
            results['errors'].append(f"Session B error: {e}")

    def session_c_worker():
        """セッションC: 20分スロット（病院C）"""
        try:
            # 病院Cのslot_infoを設定
            slot_info_c = {
                'slot_minutes': 20,
                'slot_hours': 0.333,
                'confidence': 0.85,
                'auto_detected': True
            }
            _set_current_slot_info(slot_info_c)

            # わずかに待機
            time.sleep(0.015)

            # slot_infoを取得
            retrieved = _get_current_slot_info()
            results['session_c'] = retrieved

            # 検証
            assert retrieved['slot_minutes'] == 20, f"Expected 20, got {retrieved['slot_minutes']}"
            assert retrieved['confidence'] == 0.85, f"Expected 0.85, got {retrieved['confidence']}"

        except Exception as e:
            results['errors'].append(f"Session C error: {e}")

    # 3つのスレッドを同時実行
    threads = [
        threading.Thread(target=session_a_worker, name="SessionA"),
        threading.Thread(target=session_b_worker, name="SessionB"),
        threading.Thread(target=session_c_worker, name="SessionC")
    ]

    # スレッド開始
    print("\n--- 3つのセッションを同時実行 ---")
    for t in threads:
        t.start()

    # 全スレッド完了待機
    for t in threads:
        t.join()

    # 結果検証
    print("\n--- 結果検証 ---")

    if results['errors']:
        print("[ERROR] テスト中にエラーが発生:")
        for err in results['errors']:
            print(f"  - {err}")
        return False

    # セッションAの検証
    if results['session_a']:
        print(f"[OK] セッションA: slot_minutes = {results['session_a']['slot_minutes']} (期待値: 15)")
        print(f"[OK] セッションA: confidence = {results['session_a']['confidence']} (期待値: 0.95)")
    else:
        print("[ERROR] セッションAの結果が取得できませんでした")
        return False

    # セッションBの検証
    if results['session_b']:
        print(f"[OK] セッションB: slot_minutes = {results['session_b']['slot_minutes']} (期待値: 30)")
        print(f"[OK] セッションB: auto_detected = {results['session_b']['auto_detected']} (期待値: False)")
    else:
        print("[ERROR] セッションBの結果が取得できませんでした")
        return False

    # セッションCの検証
    if results['session_c']:
        print(f"[OK] セッションC: slot_minutes = {results['session_c']['slot_minutes']} (期待値: 20)")
        print(f"[OK] セッションC: confidence = {results['session_c']['confidence']} (期待値: 0.85)")
    else:
        print("[ERROR] セッションCの結果が取得できませんでした")
        return False

    # データ混入チェック
    print("\n--- データ混入チェック ---")
    slot_a = results['session_a']['slot_minutes']
    slot_b = results['session_b']['slot_minutes']
    slot_c = results['session_c']['slot_minutes']

    if slot_a != slot_b and slot_b != slot_c and slot_a != slot_c:
        print(f"[OK] 各セッションのslot_infoが分離されています: A={slot_a}分, B={slot_b}分, C={slot_c}分")
    else:
        print(f"[ERROR] データ混入の可能性: A={slot_a}分, B={slot_b}分, C={slot_c}分")
        return False

    return True


def test_session_data_integration():
    """SessionDataとの統合テスト"""

    print("\n" + "=" * 80)
    print("Deploy 20.17: SessionDataとの統合テスト")
    print("=" * 80)

    try:
        from collections import OrderedDict
        from dash_app import ScenarioData

        # ダミーのScenarioDataを作成
        dummy_scenario = ScenarioData(name="test_scenario", root_path=Path("."))

        # SessionDataを作成（15分スロット）
        scenarios_1 = OrderedDict([("test_scenario_1", dummy_scenario)])
        session_1 = SessionData(scenarios=scenarios_1)
        session_1.slot_info = {
            'slot_minutes': 15,
            'slot_hours': 0.25,
            'confidence': 0.95,
            'auto_detected': True
        }
        session_id_1 = "test-session-15min"
        register_session(session_id_1, session_1)

        # SessionDataを作成（30分スロット）
        scenarios_2 = OrderedDict([("test_scenario_2", dummy_scenario)])
        session_2 = SessionData(scenarios=scenarios_2)
        session_2.slot_info = {
            'slot_minutes': 30,
            'slot_hours': 0.5,
            'confidence': 1.0,
            'auto_detected': False
        }
        session_id_2 = "test-session-30min"
        register_session(session_id_2, session_2)

        print("\n--- SessionData登録確認 ---")
        print(f"[OK] セッション1登録: {session_id_1}, slot_minutes={session_1.slot_info['slot_minutes']}")
        print(f"[OK] セッション2登録: {session_id_2}, slot_minutes={session_2.slot_info['slot_minutes']}")

        # SessionDataからslot_infoを取得
        retrieved_1 = get_session(session_id_1)
        retrieved_2 = get_session(session_id_2)

        print("\n--- SessionData取得確認 ---")
        assert retrieved_1 is not None, "セッション1が取得できません"
        assert retrieved_2 is not None, "セッション2が取得できません"

        print(f"[OK] セッション1取得: slot_minutes={retrieved_1.slot_info['slot_minutes']}")
        print(f"[OK] セッション2取得: slot_minutes={retrieved_2.slot_info['slot_minutes']}")

        # slot_infoが正しく分離されているか
        assert retrieved_1.slot_info['slot_minutes'] == 15, "セッション1のslot_minutesが不正"
        assert retrieved_2.slot_info['slot_minutes'] == 30, "セッション2のslot_minutesが不正"

        print("\n[OK] SessionDataのslot_infoが正しく分離されています")

        return True

    except Exception as e:
        print(f"\n[ERROR] SessionData統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Deploy 20.17: 最終検証テスト実施")
    print("=" * 80)

    # テスト1: マルチセッションslot_info分離
    test1_passed = test_multi_session_slot_info_isolation()

    # テスト2: SessionData統合
    test2_passed = test_session_data_integration()

    # 最終結果
    print("\n" + "=" * 80)
    if test1_passed and test2_passed:
        print("[OK] Deploy 20.17: 全テスト合格")
        print("=" * 80)
        print("\n確認済み:")
        print("  [OK] マルチスレッド環境でslot_infoが分離される")
        print("  [OK] SessionDataのslot_infoが正しく保持される")
        print("  [OK] データ混入が発生しない")
        sys.exit(0)
    else:
        print("[ERROR] Deploy 20.17: 一部テスト失敗")
        print("=" * 80)
        if not test1_passed:
            print("  [ERROR] マルチセッションslot_info分離テスト失敗")
        if not test2_passed:
            print("  [ERROR] SessionData統合テスト失敗")
        sys.exit(1)
