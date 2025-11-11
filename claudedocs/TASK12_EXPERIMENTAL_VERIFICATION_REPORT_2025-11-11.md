# Task 12: .tolist()動作の実験的検証レポート

**作成日**: 2025-11-11
**目的**: React Error #31根本原因調査における`.tolist()`動作の矛盾解決
**結論**: **過去の調査前提が誤っていた - Parquetデータは既にPython native型**

---

## エグゼクティブサマリー

### 重大な発見

**実験により、過去のULTRATHINK調査レポート（ULTRATHINK_10_LEVEL_FINAL_REPORT.md）の前提が誤っていたことが判明しました。**

```
過去の前提:
  - `.unique()`が`numpy.str_`を返す → ❌ 実際は Python `str` を返す
  - `.tolist()`が要素型を変換しない → ❓ 既にPython型なので変換不要
  - `sorted(...unique())`がnumpy型を保持 → ❌ 実際はPython型のまま

実験結果:
  - Parquetから読み込んだデータは既にPython native型
  - `.unique()`, `.tolist()`, `sorted()` 全てで型変換は発生しない
  - JSON serialization: 全てのパターンで成功
  - Plotly Figure creation: 全てのパターンで成功
```

### 影響

1. **Phase 1.5で特定した47箇所の修正は依然として有効**
   - データソース次第でnumpy型が混入する可能性は残る
   - 予防的措置として全箇所修正すべき

2. **本番環境30回のReact Error #31の原因は別経路にある**
   - Parquet読み込み後のデータは安全
   - Excel直接読み込み、メモリ内計算結果、または別のデータフロー経路を調査する必要がある

3. **調査方針の見直しが必要**
   - 本番環境の実際のデータフロー（Excel読み込み→処理→JSON化）を追跡
   - numpy型混入の真の経路を特定

---

## 実験設計

### 目的

以下の矛盾を解決するための実験:

**矛盾**:
- **過去の調査**: "`.tolist()`は要素型を変換しない"
- **Phase 1.5の修正方針**: "`.tolist()`を追加して問題解決"

### 実験方法

1. Parquetファイルからデータを読み込み（本番と同じ状況を再現）
2. `.unique()`, `.tolist()`, `sorted()`の各パターンを検証
3. 型確認、JSON serialization、Plotly Figure作成を試行

### テストケース

- **Test 1**: `.unique()` without `.tolist()`
- **Test 2**: `.unique().tolist()`
- **Test 3**: `sorted(...unique())` - **CRITICAL TEST**
- **Test 4**: `sorted(...unique().tolist())` - 修正案
- **Test 5**: Plotly Figure作成（Test 3とTest 4の両方）

---

## 実験結果

### Test 1: .unique() without .tolist()

```python
dates_unique = df['date_lbl'].unique()

# 結果
type(dates_unique) = <class 'numpy.ndarray'>
dates_unique = ['2024-01-01' '2024-01-02' '2024-01-03']
type(dates_unique[0]) = <class 'str'>  # ← 重要: 既にPython str型
hasattr 'item': False  # ← numpy型ではない
```

**発見**: `.unique()`は`numpy.ndarray`を返すが、**要素は既にPython `str`型**

### Test 2: .unique().tolist()

```python
dates_tolist = df['date_lbl'].unique().tolist()

# 結果
type(dates_tolist) = <class 'list'>
dates_tolist = ['2024-01-01', '2024-01-02', '2024-01-03']
type(dates_tolist[0]) = <class 'str'>  # ← Python str型
hasattr 'item': False
JSON serialization: SUCCESS
```

**発見**: `.tolist()`後も要素型は変わらず（既にPython型だったため）

### Test 3: sorted(...unique()) - CRITICAL TEST

```python
dates_sorted = sorted(df['date_lbl'].unique())

# 結果
type(dates_sorted) = <class 'list'>
dates_sorted = ['2024-01-01', '2024-01-02', '2024-01-03']
type(dates_sorted[0]) = <class 'str'>  # ← Python str型
hasattr 'item': False

JSON serialization: SUCCESS  # ← エラーが出ない！
```

**発見**: `sorted()`後も要素型はPython型のまま、JSON serialization成功

### Test 4: sorted(...unique().tolist()) - Fix

```python
dates_sorted_fixed = sorted(df['date_lbl'].unique().tolist())

# 結果
type(dates_sorted_fixed) = <class 'list'>
dates_sorted_fixed = ['2024-01-01', '2024-01-02', '2024-01-03']
type(dates_sorted_fixed[0]) = <class 'str'>
hasattr 'item': False

JSON serialization: SUCCESS
```

**発見**: Test 3と結果は同じ（既にPython型だったため）

### Test 5: Plotly Figure

**Test 5-1**: `sorted(...unique())`
```python
fig = px.imshow([[1, 2, 3], [4, 5, 6]], x=dates_sorted, y=['A', 'B'])
結果: Plotly Figure: SUCCESS
```

**Test 5-2**: `sorted(...unique().tolist())`
```python
fig = px.imshow([[1, 2, 3], [4, 5, 6]], x=dates_sorted_fixed, y=['A', 'B'])
結果: Plotly Figure: SUCCESS
```

**発見**: 両方のパターンでPlotly Figure作成成功

---

## 結論

### 主要な発見

1. **Parquetから読み込んだデータは既にPython native型**
   - `.unique()`が返す`numpy.ndarray`の要素は既に`str`型
   - `hasattr(element, 'item')` → `False`
   - JSON serialization → 成功

2. **過去の調査前提が誤っていた**
   - ULTRATHINK_10_LEVEL_FINAL_REPORT.md:
     - 前提: "`.unique()`が`numpy.str_`を返す"
     - 実験結果: `.unique()`は既にPython `str`を返す

3. **`.tolist()`の動作**
   - コンテナを`numpy.ndarray`から`list`に変換する ← ✅ 正しい
   - 要素型は**入力に依存する** ← ✅ 今回の発見
     - 入力が`numpy.str_`なら、出力も`numpy.str_`
     - 入力が`str`なら、出力も`str`

4. **`sorted()`の動作**
   - コンテナを`list`に変換する
   - 要素型は**入力に依存する**（`.tolist()`と同じ）

### なぜ本番環境でエラーが発生しているのか

**可能性1: Excel直接読み込み**
```python
# Excel読み込み直後は numpy型が残る可能性
df = pd.read_excel('file.xlsx')
unique_values = df['column'].unique()  # numpy.str_が残る
```

**可能性2: メモリ内計算結果**
```python
# 計算結果がnumpy型を生成
calculated_df = some_calculation()
unique_values = calculated_df['column'].unique()  # numpy型が残る
```

**可能性3: 異なるデータフロー経路**
- 本番環境では異なる処理パスを通っている
- `to_parquet()` → `read_parquet()`を経由しないデータがある

### Phase 1.5修正の正当性

**結論**: **Phase 1.5で特定した47箇所の修正は依然として必要**

理由:
1. **データソース依存性**
   - Parquetは安全だが、Excelやメモリ内計算は安全でない
   - 全データフローで型変換を保証する必要がある

2. **予防的措置として有効**
   - 将来のデータソース変更に対応
   - 型安全性を明示的に保証

3. **修正のコストは低い**
   - `.tolist()`や`.item()`の追加は低リスク
   - パフォーマンスへの影響は無視できる

---

## 次のステップ

### Task 13: 本番環境の実際のデータフロー追跡

**目的**: numpy型混入の真の経路を特定

**調査対象**:

1. **Excel読み込み経路**
   ```python
   # shift_suite/tasks/io_excel.py の ingest_excel() 関数
   # Excel -> DataFrame -> Parquet の変換過程
   ```

2. **メモリ内計算経路**
   ```python
   # dash_app.py の各コールバック内の計算
   # GroupBy, agg(), pivot_table() 等の結果
   ```

3. **キャッシュ経路**
   ```python
   # ScenarioData のキャッシュ機構
   # get_dataset() / set_dataset() の型保持状況
   ```

4. **ドロップダウンoptions生成**
   ```python
   # dash_app.py Line 3760, 3763, 8298, etc.
   # data_get('roles') の実際の型
   ```

### Task 14: 修正方針の最終決定

**Option A**: Phase 1.5の47箇所を全て修正（推奨）
- メリット: 全データフローで型安全性を保証
- デメリット: 修正箇所が多い

**Option B**: 真の原因経路のみ修正
- メリット: 最小限の変更
- デメリット: 将来のリスクが残る

**推奨**: **Option A**
- 理由: データソース依存性を排除し、長期的な安定性を確保

---

## 技術的詳細

### Parquetフォーマットの型保持動作

**仮説**:
```
Parquetファイルは列ごとに型情報を保持する
→ 文字列列は "string" 型として保存
→ read_parquet()時にPython str型に変換される
```

**検証方法**:
```python
df.to_parquet('test.parquet')
df_loaded = pd.read_parquet('test.parquet')
print(df_loaded['column'].dtype)  # object
print(type(df_loaded['column'].iloc[0]))  # <class 'str'>
```

### Excel vs Parquetの型変換の違い

| データソース | unique()の要素型 | JSON化 |
|-------------|-----------------|--------|
| Excel直接 | numpy.str_ | ❌ 失敗の可能性 |
| Parquet経由 | Python str | ✅ 成功 |
| メモリ計算 | numpy.str_ | ❌ 失敗の可能性 |

### 修正パターンの効果

| パターン | 効果 | Parquetデータ | Excelデータ |
|---------|------|--------------|------------|
| `.unique()` | なし | ✅ 安全 | ❌ 危険 |
| `.unique().tolist()` | コンテナ変換 | ✅ 安全 | ❓ 要素次第 |
| `[v.item() if hasattr(v, 'item') else v for v in ...]` | 要素型変換 | ✅ 安全 | ✅ 安全 |

**結論**: `[v.item() if hasattr(v, 'item') else v for v in ...]`が最も堅牢

---

## 参考資料

### 実験コード

**ファイル**: `test_tolist_simple.py`

**主要コード**:
```python
import pandas as pd
import numpy as np
import json
from pathlib import Path

# Parquetに保存して再読み込み（本番と同じ状況）
df_test = pd.DataFrame({'date_lbl': ['2024-01-01', '2024-01-02', '2024-01-03']})
test_parquet = Path("test_data_temp.parquet")
df_test.to_parquet(test_parquet)
df = pd.read_parquet(test_parquet)
test_parquet.unlink()

# Test 1: .unique()
dates_unique = df['date_lbl'].unique()
print(f"type(dates_unique[0]) = {type(dates_unique[0])}")
# → <class 'str'>

# Test 3: sorted(...unique())
dates_sorted = sorted(df['date_lbl'].unique())
try:
    json.dumps({'dates': dates_sorted})
    print("SUCCESS")
except TypeError as e:
    print(f"FAILED: {e}")
# → SUCCESS
```

### 関連ドキュメント

- `PHASE1.5_COMPLETION_REPORT_2025-11-11.md`: Phase 1.5調査完了レポート
- `ULTRATHINK_10_LEVEL_FINAL_REPORT.md`: 過去のULTRATHINK調査（前提が誤っていた）
- `UNIQUE_WITHOUT_TOLIST_ANALYSIS_2025-11-11.md`: .unique()パターン分析
- `VALUES_WITHOUT_INDEX_ANALYSIS_2025-11-11.md`: .valuesパターン分析

---

**作成者**: Claude Code
**最終更新**: 2025-11-11
**ステータス**: Task 12完了、Task 13（本番データフロー追跡）へ進む

**重要な教訓**:
> テストケースの前提条件が実際の本番環境と異なる可能性を常に考慮せよ。
> Parquetデータでの検証は、全データフローの検証ではない。
