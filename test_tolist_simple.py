"""
Task 12: .tolist()の動作を実験的に検証（簡易版）
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

print("=" * 80)
print("Task 12: .tolist()動作の実験的検証")
print("=" * 80)

# サンプルデータ作成
df_test = pd.DataFrame({
    'date_lbl': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-01', '2024-01-02'],
    'staff': ['職員A', '職員B', '職員C', '職員A', '職員B'],
    'value': [10, 20, 30, 15, 25]
})

# Parquetに保存して再読み込み（本番と同じ状況）
test_parquet = Path("test_data_temp.parquet")
df_test.to_parquet(test_parquet)
df = pd.read_parquet(test_parquet)
test_parquet.unlink()

print(f"\nDataFrame shape: {df.shape}")
print(f"DataFrame dtypes:\n{df.dtypes}")

# ======================================================================
# Test 1: .unique() without .tolist()
# ======================================================================
print("\n" + "=" * 80)
print("Test 1: .unique() without .tolist()")
print("=" * 80)

dates_unique = df['date_lbl'].unique()

print(f"\ntype(dates_unique) = {type(dates_unique)}")
print(f"dates_unique = {dates_unique}")
if len(dates_unique) > 0:
    print(f"type(dates_unique[0]) = {type(dates_unique[0])}")
    print(f"hasattr 'item': {hasattr(dates_unique[0], 'item')}")

# ======================================================================
# Test 2: .unique().tolist()
# ======================================================================
print("\n" + "=" * 80)
print("Test 2: .unique().tolist()")
print("=" * 80)

dates_tolist = df['date_lbl'].unique().tolist()

print(f"\ntype(dates_tolist) = {type(dates_tolist)}")
print(f"dates_tolist = {dates_tolist}")
if len(dates_tolist) > 0:
    print(f"type(dates_tolist[0]) = {type(dates_tolist[0])}")
    print(f"hasattr 'item': {hasattr(dates_tolist[0], 'item')}")

# JSON serialization
try:
    json.dumps({'dates': dates_tolist})
    print("JSON serialization: SUCCESS")
except TypeError as e:
    print(f"JSON serialization: FAILED - {e}")

# ======================================================================
# Test 3: sorted(...unique()) - CRITICAL TEST
# ======================================================================
print("\n" + "=" * 80)
print("Test 3: sorted(...unique()) - CRITICAL TEST")
print("=" * 80)

dates_sorted = sorted(df['date_lbl'].unique())

print(f"\ntype(dates_sorted) = {type(dates_sorted)}")
print(f"dates_sorted = {dates_sorted}")
if len(dates_sorted) > 0:
    print(f"type(dates_sorted[0]) = {type(dates_sorted[0])}")
    print(f"hasattr 'item': {hasattr(dates_sorted[0], 'item')}")

# JSON serialization
print("\nJSON serialization:")
try:
    json.dumps({'dates': dates_sorted})
    print("  SUCCESS")
except TypeError as e:
    print(f"  FAILED: {e}")
    print("  !! This is the root cause of React Error #31 !!")

# ======================================================================
# Test 4: sorted(...unique().tolist()) - Fix
# ======================================================================
print("\n" + "=" * 80)
print("Test 4: sorted(...unique().tolist()) - Fix")
print("=" * 80)

dates_sorted_fixed = sorted(df['date_lbl'].unique().tolist())

print(f"\ntype(dates_sorted_fixed) = {type(dates_sorted_fixed)}")
print(f"dates_sorted_fixed = {dates_sorted_fixed}")
if len(dates_sorted_fixed) > 0:
    print(f"type(dates_sorted_fixed[0]) = {type(dates_sorted_fixed[0])}")
    print(f"hasattr 'item': {hasattr(dates_sorted_fixed[0], 'item')}")

# JSON serialization
print("\nJSON serialization:")
try:
    json.dumps({'dates': dates_sorted_fixed})
    print("  SUCCESS")
except TypeError as e:
    print(f"  FAILED: {e}")

# ======================================================================
# Test 5: Plotly Figure
# ======================================================================
print("\n" + "=" * 80)
print("Test 5: Plotly Figure")
print("=" * 80)

try:
    import plotly.express as px

    # Test 5-1: sorted(...unique())
    print("\nTest 5-1: sorted(...unique())")
    try:
        fig = px.imshow(
            [[1, 2, 3], [4, 5, 6]],
            x=dates_sorted[:3] if len(dates_sorted) >= 3 else dates_sorted,
            y=['A', 'B']
        )
        fig_json = fig.to_json()
        print("  Plotly Figure: SUCCESS")
    except Exception as e:
        print(f"  Plotly Figure: FAILED - {type(e).__name__}: {e}")
        print("  !! This is the root cause of React Error #31 !!")

    # Test 5-2: sorted(...unique().tolist())
    print("\nTest 5-2: sorted(...unique().tolist())")
    try:
        fig = px.imshow(
            [[1, 2, 3], [4, 5, 6]],
            x=dates_sorted_fixed[:3] if len(dates_sorted_fixed) >= 3 else dates_sorted_fixed,
            y=['A', 'B']
        )
        fig_json = fig.to_json()
        print("  Plotly Figure: SUCCESS")
    except Exception as e:
        print(f"  Plotly Figure: FAILED - {type(e).__name__}: {e}")

except ImportError:
    print("Plotly not installed, skipping Plotly tests")

# ======================================================================
# 最終結論
# ======================================================================
print("\n" + "=" * 80)
print("最終結論")
print("=" * 80)

print("""
1. .unique() の挙動:
   - 返り値: numpy.ndarray
   - 要素: Parquetから読み込んだ場合、既にPython str型

2. .unique().tolist() の挙動:
   - 返り値: Python list
   - 要素: Python native型
   - JSON serialization: 成功

3. sorted(...unique()) の挙動 (CRITICAL):
   - 返り値: Python list
   - 要素: 入力データ次第（Parquetの場合は既にstr）
   - JSON serialization: 成功する場合もある

4. sorted(...unique().tolist()) の挙動 (Fix):
   - 返り値: Python list
   - 要素: Python native型
   - JSON serialization: 成功

重要な発見:
- Parquetから読み込んだデータは既にPython型の可能性がある
- しかし、本番環境では異なる挙動を示している可能性
- Excel -> Parquet変換時にnumpy型が混入する可能性

次のステップ:
- 実際の本番データ（aggregated_df.parquet）で検証が必要
""")

print("\n" + "=" * 80)
print("実験完了")
print("=" * 80)
