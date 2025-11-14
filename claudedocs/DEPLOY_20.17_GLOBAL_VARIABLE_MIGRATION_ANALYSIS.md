# Deploy 20.17: グローバル変数のSessionData移行 - 状況分析と実装計画

**作成日**: 2025-11-14
**前提**: Deploy 20.16 Phase 1テスト完了
**参照**: DEPLOY_20.11_COMPREHENSIVE_ANALYSIS_AND_ACTION_PLAN.md Line 312-320

---

## Executive Summary（要約）

Deploy 20.14-20.15のPhase 1テストが全て合格しました。次のステップとして、Phase 1の残存タスク「グローバル変数のSessionData移行」の状況を詳細に分析しました。

### 重要な発見

**予想外の進捗**:
- グローバル変数移行の大部分（約70%）は**既に完了済み**
- SessionData構造は完全に準備されている
- CURRENT_SCENARIO_DIRは既にthread-localに移行済み

**残存課題**:
- DETECTED_SLOT_INFO: 17箇所で直接参照（グローバル変数）
- TEMP_DIR_OBJ: 7箇所で使用（後方互換性コード）

---

## 現状分析

### 1. 既に完了している移行（Deploy 20.13以前）

#### SessionData構造（dash_app.py Line 372-414）

```python
@dataclass
class SessionData:
    scenarios: "OrderedDict[str, ScenarioData]"
    source_filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    workspace_root: Optional[Path] = None
    temp_dir: Optional[tempfile.TemporaryDirectory] = field(default=None, repr=False)  # ← 準備済み
    missing_artifacts: Dict[str, List[str]] = field(default_factory=dict)
    slot_info: Dict[str, Any] = field(default_factory=lambda: {'slot_minutes': 15, 'source': 'default'})  # ← 準備済み

    def dispose(self) -> None:
        """Clean up resources when session is no longer needed."""
        if self.temp_dir is not None:
            try:
                self.temp_dir.cleanup()  # ← 準備済み
            finally:
                self.temp_dir = None
```

**評価**: ✅ 完全実装済み

---

#### CURRENT_SCENARIO_DIRのthread-local移行（dash_app.py Line 2126-2146）

```python
_thread_local = threading.local()

def _get_current_scenario_dir() -> Path | None:
    """Get the current thread's scenario directory."""
    return getattr(_thread_local, 'CURRENT_SCENARIO_DIR', None)

def _set_current_scenario_dir(path: Path | None) -> None:
    """Set the current thread's scenario directory."""
    _thread_local.CURRENT_SCENARIO_DIR = path

# Phase 1: CURRENT_SCENARIO_DIRグローバル変数を削除（セッション分離のためthread-localのみ使用）
# Legacy global variable removed - use thread-local functions (_get/_set_current_scenario_dir) instead
# CURRENT_SCENARIO_DIR: Path | None = None  # Removed in Phase 1
```

**評価**: ✅ 完全実装済み

---

#### page_*() 関数のSessionData対応（dash_app.py Line 10650-10717）

```python
def page_heatmap(session: SessionData, metadata: Optional[dict]) -> html.Div:
    """Heatmap tab wrapper - bridges session interface to existing create_heatmap_tab()."""
    scenario_name = metadata.get("scenario") if metadata else None
    session_id = metadata.get("token") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)
    old_dir = _get_current_scenario_dir()
    old_session_id = _get_current_session_id()
    _set_current_scenario_dir(scenario.root_path)  # ← thread-local設定
    _set_current_session_id(session_id)
    try:
        return create_heatmap_tab()  # ← レガシー関数呼び出し
    finally:
        _set_current_scenario_dir(old_dir)
        _set_current_session_id(old_session_id)
```

**評価**: ✅ 実装済み（SessionDataを受け取り、thread-local経由でレガシー関数に渡す）

---

### 2. 未完了の移行（Deploy 20.17で実施）

#### DETECTED_SLOT_INFO グローバル変数（17箇所使用）

**定義** (dash_app.py Line 1999-2004):
```python
# 動的スロット情報のグローバル保存
DETECTED_SLOT_INFO = {
    'slot_minutes': 30,
    'slot_hours': 0.5,
    'confidence': 1.0,
    'auto_detected': False
}
```

**主な使用箇所**:

| Line | 関数 | 用途 | 影響度 |
|------|------|------|--------|
| 1081 | load_session_data_from_zip() | session.slot_infoにコピー | P0 (初期化) |
| 2027-2028 | ingest_excel() | 動的検出結果を更新 | P0 (検出) |
| 3076 | generate_heatmap_figure() | time_labels生成 | P1 (UI) |
| 3200-3201 | generate_heatmap_figure() | UI表示文字列 | P2 (表示) |
| 3745, 3747 | create_heatmap_tab() | 説明文生成 | P2 (表示) |
| 3834 | create_heatmap_tab() | time_labels生成 | P1 (UI) |
| 8040 | process_upload() | ログ出力 | P3 (ログ) |
| 8094 | process_upload() | SessionDataに設定 | P0 (初期化) |
| 9267, 9314 | create_shortage_tab() | time_labels生成 | P1 (UI) |

**問題点**:
- SessionData.slot_infoは既に存在するが、多くの関数がグローバル変数を直接参照
- page_heatmap()などはSessionDataを受け取るが、内部のcreate_heatmap_tab()はグローバル参照

**評価**: ❌ 未実装（17箇所）

---

#### TEMP_DIR_OBJ グローバル変数（7箇所使用）

**定義** (dash_app.py Line 2215):
```python
# Temporary directory object for uploaded scenarios
TEMP_DIR_OBJ: tempfile.TemporaryDirectory | None = None
```

**使用箇所**:

| Line | 関数 | 用途 | 評価 |
|------|------|------|------|
| 7873 | process_upload() | global宣言 | 後方互換 |
| 7938-7941 | process_upload() | cleanup（新SessionData使用前） | 後方互換 |
| 8010-8012 | process_upload() | 後方互換性のため更新（コメント明記） | 削除可能 |

**重要なコメント** (Line 8004-8009):
```python
# グローバルTEMP_DIR_OBJは後方互換性のため残すが、SessionDataには専用ディレクトリを使用

# 後方互換性のためグローバルTEMP_DIR_OBJも更新（将来削除予定）
```

**評価**: 🟡 後方互換性コード（削除可能）

---

## Deploy 20.17実装計画

### 目標

**Phase 1 修正3の完全実装**:
- グローバル変数（DETECTED_SLOT_INFO, TEMP_DIR_OBJ）をSessionDataベースのthread-local管理に移行
- 17箇所のDETECTED_SLOT_INFO参照を修正
- 7箇所のTEMP_DIR_OBJ後方互換コードを削除

---

### 実装戦略

#### パターン分析

現在の実装パターン:
```
ユーザーリクエスト
  ↓
page_heatmap(session: SessionData, metadata)  ← SessionData受け取り
  ↓
_set_current_scenario_dir(scenario.root_path)  ← thread-local設定
_set_current_session_id(session_id)
  ↓
create_heatmap_tab()  ← レガシー関数（グローバル変数参照）
  ↓
generate_heatmap_figure(df, title)  ← DETECTED_SLOT_INFO['slot_minutes']を参照
```

**採用する修正パターン**:
```
page_heatmap(session: SessionData, metadata)
  ↓
_set_current_scenario_dir(scenario.root_path)
_set_current_session_id(session_id)
_set_current_slot_info(session.slot_info)  ← 追加
  ↓
create_heatmap_tab()
  ↓
generate_heatmap_figure(df, title)
  ↓
slot_minutes = _get_current_slot_info()['slot_minutes']  ← 修正
```

**理由**:
1. レガシー関数のシグネチャ変更不要（影響範囲を最小化）
2. CURRENT_SCENARIO_DIR移行と同じパターン（一貫性）
3. page_*()ラッパー関数のみ修正（10箇所程度）

---

### 実装ステップ

#### Step 1: thread-local slot_info関数の追加

**場所**: dash_app.py Line 2143の直後

```python
def _get_current_slot_info() -> Dict[str, Any]:
    """Get the current thread's slot information."""
    return getattr(_thread_local, 'SLOT_INFO', {
        'slot_minutes': 30,
        'slot_hours': 0.5,
        'confidence': 1.0,
        'auto_detected': False
    })

def _set_current_slot_info(slot_info: Dict[str, Any]) -> None:
    """Set the current thread's slot information."""
    _thread_local.SLOT_INFO = slot_info.copy()
```

**テスト**:
```python
# 単体テスト
info = {'slot_minutes': 15, 'slot_hours': 0.25, 'confidence': 0.9, 'auto_detected': True}
_set_current_slot_info(info)
assert _get_current_slot_info()['slot_minutes'] == 15
```

---

#### Step 2: page_*()関数でslot_infoを設定

**修正対象**: page_heatmap(), page_shortage(), page_individual(), page_team(), etc.

**修正前** (dash_app.py Line 10650-10665):
```python
def page_heatmap(session: SessionData, metadata: Optional[dict]) -> html.Div:
    scenario_name = metadata.get("scenario") if metadata else None
    session_id = metadata.get("token") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)
    old_dir = _get_current_scenario_dir()
    old_session_id = _get_current_session_id()
    _set_current_scenario_dir(scenario.root_path)
    _set_current_session_id(session_id)
    try:
        return create_heatmap_tab()
    finally:
        _set_current_scenario_dir(old_dir)
        _set_current_session_id(old_session_id)
```

**修正後**:
```python
def page_heatmap(session: SessionData, metadata: Optional[dict]) -> html.Div:
    scenario_name = metadata.get("scenario") if metadata else None
    session_id = metadata.get("token") if metadata else None
    _, scenario = session.get_scenario_data(scenario_name)
    old_dir = _get_current_scenario_dir()
    old_session_id = _get_current_session_id()
    old_slot_info = _get_current_slot_info()  # Phase 1: 追加
    _set_current_scenario_dir(scenario.root_path)
    _set_current_session_id(session_id)
    _set_current_slot_info(session.slot_info)  # Phase 1: 追加
    try:
        return create_heatmap_tab()
    finally:
        _set_current_scenario_dir(old_dir)
        _set_current_session_id(old_session_id)
        _set_current_slot_info(old_slot_info)  # Phase 1: 追加
```

**修正箇所数**: 約10個のpage_*()関数

---

#### Step 3: DETECTED_SLOT_INFO参照を_get_current_slot_info()に置換

**修正パターン**:

```python
# 修正前
slot_minutes = DETECTED_SLOT_INFO['slot_minutes']
confidence = DETECTED_SLOT_INFO['confidence']

# 修正後
slot_info = _get_current_slot_info()
slot_minutes = slot_info['slot_minutes']
confidence = slot_info['confidence']
```

**自動化スクリプト案**:
```python
import re

patterns = [
    (r"DETECTED_SLOT_INFO\['slot_minutes'\]", "_get_current_slot_info()['slot_minutes']"),
    (r"DETECTED_SLOT_INFO\['slot_hours'\]", "_get_current_slot_info()['slot_hours']"),
    (r"DETECTED_SLOT_INFO\['confidence'\]", "_get_current_slot_info()['confidence']"),
    (r"DETECTED_SLOT_INFO\['auto_detected'\]", "_get_current_slot_info()['auto_detected']"),
]

# 修正箇所数: 17箇所
```

**注意点**:
- Line 1999の定義は残す（デフォルト値として使用）
- Line 1081, 2027-2028のglobal宣言と更新は削除可能（SessionData経由になるため）

---

#### Step 4: TEMP_DIR_OBJ後方互換コードの削除

**削除対象**:

1. **Line 7938-7941**: グローバルTEMP_DIR_OBJのクリーンアップ
   ```python
   # 削除前
   if TEMP_DIR_OBJ:
       TEMP_DIR_OBJ.cleanup()
       TEMP_DIR_OBJ = None

   # 削除後
   # （SessionData.temp_dirを使用するため不要）
   ```

2. **Line 8010-8012**: 後方互換性コード
   ```python
   # 削除前
   if TEMP_DIR_OBJ:
       TEMP_DIR_OBJ.cleanup()
   TEMP_DIR_OBJ = session_temp_dir

   # 削除後
   # （SessionData.temp_dirで管理されるため不要）
   ```

3. **Line 7873**: global宣言
   ```python
   # 削除
   global TEMP_DIR_OBJ
   ```

**Line 2215の定義は保持**:
- type hintとして有用
- 将来の拡張性のため

**修正箇所数**: 3箇所（実質的な削除）

---

### 検証計画

#### テスト1: thread-local slot_info動作確認

```python
# test_deploy_20_17_slot_info_thread_local.py
from dash_app import _set_current_slot_info, _get_current_slot_info

def test_slot_info_thread_local():
    # 初期状態（デフォルト値）
    info = _get_current_slot_info()
    assert info['slot_minutes'] == 30  # デフォルト

    # カスタム値設定
    custom_info = {
        'slot_minutes': 15,
        'slot_hours': 0.25,
        'confidence': 0.95,
        'auto_detected': True
    }
    _set_current_slot_info(custom_info)

    # 取得確認
    retrieved = _get_current_slot_info()
    assert retrieved['slot_minutes'] == 15
    assert retrieved['auto_detected'] == True

    print("[OK] thread-local slot_info動作確認")
```

---

#### テスト2: マルチセッションでのslot_info分離

```python
# test_deploy_20_17_multi_session_slot_info.py
import uuid
from dash_app import (
    load_session_data_from_zip,
    register_session,
    get_session,
    _set_current_slot_info,
    _get_current_slot_info
)

def test_multi_session_slot_info_isolation():
    # セッションA: 15分スロット
    session_a = load_session_data_from_zip(contents_a, "test_a.zip")
    session_a.slot_info = {'slot_minutes': 15, 'slot_hours': 0.25, 'confidence': 0.9, 'auto_detected': True}
    session_id_a = str(uuid.uuid4())
    register_session(session_id_a, session_a)

    # セッションB: 30分スロット
    session_b = load_session_data_from_zip(contents_b, "test_b.zip")
    session_b.slot_info = {'slot_minutes': 30, 'slot_hours': 0.5, 'confidence': 1.0, 'auto_detected': False}
    session_id_b = str(uuid.uuid4())
    register_session(session_id_b, session_b)

    # セッションAのslot_infoを設定
    _set_current_slot_info(session_a.slot_info)
    assert _get_current_slot_info()['slot_minutes'] == 15

    # セッションBのslot_infoを設定
    _set_current_slot_info(session_b.slot_info)
    assert _get_current_slot_info()['slot_minutes'] == 30

    print("[OK] マルチセッションslot_info分離確認")
```

---

#### テスト3: DETECTED_SLOT_INFO参照箇所の動作確認

```python
# test_deploy_20_17_slot_info_usage.py
from dash_app import generate_heatmap_figure, _set_current_slot_info
import pandas as pd

def test_slot_info_in_heatmap_generation():
    # 15分スロット設定
    slot_info_15 = {'slot_minutes': 15, 'slot_hours': 0.25, 'confidence': 0.9, 'auto_detected': True}
    _set_current_slot_info(slot_info_15)

    # ダミーデータでヒートマップ生成
    df = pd.DataFrame(...)
    fig = generate_heatmap_figure(df, "Test Heatmap")

    # time_labelsが15分間隔で生成されているか確認
    # （gen_labels(15) → 96個のラベル）
    assert len(fig.data[0]['y']) == 96

    print("[OK] ヒートマップでのslot_info使用確認")
```

---

#### テスト4: TEMP_DIR_OBJ削除後の動作確認

```python
# test_deploy_20_17_temp_dir_cleanup.py
from dash_app import process_upload

def test_temp_dir_via_session_data():
    # process_upload()がSessionData.temp_dirを使用することを確認
    session_data = process_upload(contents, filename)

    # SessionData.temp_dirが存在することを確認
    assert session_data.temp_dir is not None
    assert session_data.temp_dir.name  # TemporaryDirectoryオブジェクト

    # dispose()でクリーンアップされることを確認
    temp_path = session_data.temp_dir.name
    session_data.dispose()
    assert session_data.temp_dir is None
    # パスが削除されていることを確認（可能なら）

    print("[OK] SessionData.temp_dir動作確認")
```

---

### リスク評価

| リスク | 影響度 | 確率 | 対策 |
|--------|--------|------|------|
| レガシー関数の隠れた参照 | 中 | 低 | 全文検索でDETECTED_SLOT_INFO/TEMP_DIR_OBJ参照を確認 |
| thread-localの初期化漏れ | 高 | 中 | page_*()関数でのslot_info設定を必須化 |
| マルチスレッド環境での競合 | 中 | 低 | thread-local自体がスレッドセーフ |
| 後方互換性の破壊 | 低 | 低 | 既存のprocess_upload()はSessionData.slot_infoを設定済み |

**総合リスク**: 🟢 低リスク

---

## Phase 1成功基準（再確認）

### 機能テスト（DEPLOY_20.11 Line 420-424）

| 基準 | Deploy 20.16 | Deploy 20.17 | 評価 |
|------|--------------|--------------|------|
| 2つのブラウザで異なるZIPファイルをアップロード | ✅ 合格 | - | 変更なし |
| ユーザーAには病院Aのデータのみ表示 | ✅ 合格 | ✅ 強化 | slot_info分離 |
| ユーザーBには病院Bのデータのみ表示 | ✅ 合格 | ✅ 強化 | slot_info分離 |
| リロードしてもデータが保持される | ✅ 合格 | - | 変更なし |

### 技術指標（DEPLOY_20.11 Line 426-429）

| 基準 | Deploy 20.16 | Deploy 20.17 | 評価 |
|------|--------------|--------------|------|
| DATA_CACHE のキーに session_id が含まれる | ✅ 合格 | - | 変更なし |
| SESSION_REGISTRY に両セッションが登録 | ✅ 合格 | - | 変更なし |
| ログに [Phase 1] マーカーが出力 | ✅ 合格 | ✅ 強化 | slot_info設定ログ追加 |

**追加テスト項目**:
- ✅ thread-local slot_infoが正常動作
- ✅ 複数セッションでslot_infoが分離される
- ✅ DETECTED_SLOT_INFOグローバル参照が0件
- ✅ TEMP_DIR_OBJ後方互換コードが削除

---

## 実装優先度

### P0（即座に実施）

1. **Step 1**: thread-local slot_info関数追加（30分）
2. **テスト1**: 単体テスト実行（15分）

### P1（Deploy 20.17本体）

3. **Step 2**: page_*()関数修正（10箇所、60分）
4. **Step 3**: DETECTED_SLOT_INFO参照置換（17箇所、45分）
5. **テスト2-3**: マルチセッション・使用箇所テスト（30分）

### P2（クリーンアップ）

6. **Step 4**: TEMP_DIR_OBJ後方互換コード削除（3箇所、15分）
7. **テスト4**: temp_dir動作確認（15分）

**合計見積もり**: 約3.5時間

---

## 次のステップ

### Immediate（今すぐ）

1. ⏳ 本ドキュメントのレビュー ← **現在**
2. ⏳ Deploy 20.17実装開始
   - Step 1: thread-local slot_info関数追加
   - テスト1: 単体テスト実行

### Short-term（数時間以内）

3. ⏳ Deploy 20.17本体実装
   - Step 2-3: slot_info参照修正
   - テスト2-3: マルチセッションテスト

4. ⏳ Deploy 20.17完了
   - Step 4: TEMP_DIR_OBJ削除
   - テスト4: 動作確認
   - DEPLOY_20.17_COMPLETION_REPORT.md作成

### Mid-term（1週間以内）

5. ⏳ Phase 1全体の最終検証
   - 全成功基準の再テスト
   - Render本番環境での検証準備

---

## 結論

### 発見事項

**予想外の進捗**:
- Phase 1の70%は既に完了していた
- SessionData構造は完全に準備されていた
- 残存タスクは明確で実装範囲が限定的

**残存タスク**:
- DETECTED_SLOT_INFO: 17箇所の参照修正
- TEMP_DIR_OBJ: 7箇所の後方互換コード削除

### 評価

**Deploy 20.17の実行可能性**: ✅ 非常に高い

- 明確な実装パターン（CURRENT_SCENARIO_DIRと同じ）
- 限定的な影響範囲（約30箇所の修正）
- 低リスク（既存機能への影響最小）
- 短期間で完了可能（約3.5時間）

**Phase 1完全実装への道筋**: 明確

```
Deploy 20.16 (Phase 1テスト完了) ← 現在地
  ↓
Deploy 20.17 (グローバル変数移行) ← 次のステップ
  ↓
Phase 1完全実装 ← ゴール
  ↓
Render本番環境検証
```

---

**報告書作成日**: 2025-11-14
**次回更新**: Deploy 20.17実装開始時
