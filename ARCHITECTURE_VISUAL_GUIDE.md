# システムアーキテクチャ ビジュアルガイド v5.1

**最終更新**: 2025-10-01
**目的**: 全16図を1つのドキュメントでまとめて閲覧
**推奨表示**: VS Code Mermaid Preview拡張機能、または GitHub

---

## 📚 目次

### 基盤アーキテクチャ（図1-3）
1. [全体システムアーキテクチャ](#1-全体システムアーキテクチャv50拡張版)
2. [エンジン自動切り替えフロー](#2-エンジン自動切り替えフロー)
3. [OR-Toolsエンジン詳細](#3-or-toolsエンジン詳細アーキテクチャ)

### コア機能（図4-8）
4. [マルチシナリオ生成フロー](#4-マルチシナリオ生成フロー)
5. [データフロー図](#5-データフロー図excel--出力)
6. [コンポーネント関係図](#6-コンポーネント関係図)
7. [戦略別重み調整マトリクス](#7-戦略別重み調整マトリクス)
8. [6軸評価システム](#8-6軸評価システム)

### 運用・テスト（図9-10）
9. [テストアーキテクチャ](#9-テストアーキテクチャ)
10. [デプロイメント構成](#10-デプロイメント構成シンプル版)

### AI連携（図11-12）
11. [対話ループフロー](#11-対話ループフローai連携)
12. [AI-システム責任分担図](#12-ai-システム責任分担図)

### モード管理 v5.1（図13-16）
13. [モードベースアクセス制御フロー](#13-モードベースアクセス制御フロー)
14. [モード別権限マトリクス](#14-モード別権限マトリクス)
15. [モード切り替えシーケンス](#15-モード切り替えシーケンス)
16. [全体アーキテクチャ（モード統合版）](#16-全体アーキテクチャモード統合版)

---

# 基盤アーキテクチャ

## 1. 全体システムアーキテクチャ（v5.0拡張版）

**概要**: システム全体の層構造とデータフロー

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "AI対話層（Claude Code / Gemini CLI等）"
        AI[AI Agent<br/>自然言語理解・対話管理]
    end

    subgraph "ユーザー"
        U[介護施設管理者]
    end

    subgraph "入力"
        E[Excel設定ファイル<br/>施設情報・スタッフ・制約等]
    end

    subgraph "エンジン選択層"
        FSA[FlexibleSystemAdapter<br/>エンジン自動判定]
        MSG[MultiScenarioGenerator<br/>複数戦略同時生成]
    end

    subgraph "OR-Toolsエンジン"
        OSG[ShiftGenerator<br/>CP-SAT最適化]
        CI[ConstraintImplementor<br/>11種類の制約]
        OFM[ObjectiveFunctionManager<br/>目的関数生成]
        SE[ScenarioEvaluator<br/>6軸評価]
    end

    subgraph "カスタムアルゴリズムエンジン"
        CSS[ConsolidatedShiftSystem<br/>軽量・高速アルゴリズム]
    end

    subgraph "出力"
        OUT[シフト結果Excel<br/>評価レポート]
        SCORE[スコアリング結果<br/>違反ルール詳細]
    end

    U <-->|自然言語対話| AI
    AI -->|Excel読み込み指示| E
    AI -->|Python実行| FSA
    E --> FSA
    FSA --> MSG
    MSG -->|戦略1-5| OSG
    FSA -->|OR_Tools_Config=True| OSG
    FSA -->|OR_Tools_Config=False/なし| CSS

    OSG --> CI
    OSG --> OFM
    OSG --> SE

    CI --> OUT
    SE --> SCORE
    CSS --> OUT
    OUT --> AI
    SCORE --> AI
    AI -->|結果報告<br/>修正提案| U
    AI -.->|制約追加<br/>重み変更| E

    style AI fill:#884444,stroke:#999,stroke-width:4px
    style FSA fill:#886633,stroke:#999,stroke-width:3px
    style MSG fill:#664488,stroke:#999,stroke-width:2px
    style OSG fill:#336688,stroke:#999,stroke-width:2px
    style CSS fill:#338844,stroke:#999,stroke-width:2px
    style SCORE fill:#447788,stroke:#999,stroke-width:2px
```

**ポイント**:
- AI層が自然言語を理解してPython実行
- 2つのエンジン（OR-Tools/カスタム）を自動選択
- 複数シナリオ同時生成が可能
- 6軸評価で品質を保証

---

## 2. エンジン自動切り替えフロー

**概要**: OR-Toolsエンジンとカスタムアルゴリズムの選択ロジック

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
flowchart TD
    Start([シフト生成開始]) --> LoadExcel[Excel設定ファイル読み込み]
    LoadExcel --> CheckSheet{OR_Tools_Config<br/>シート存在?}

    CheckSheet -->|Yes| CheckFlag{B2セル<br/>= True?}
    CheckSheet -->|No| UseCustom[カスタムアルゴリズム使用]

    CheckFlag -->|True| UseORTools[OR-Toolsエンジン使用]
    CheckFlag -->|False| UseCustom

    UseORTools --> ConvertData[v4.0 Excel → OR-Tools形式変換]
    ConvertData --> RunORTools[CP-SAT最適化実行]
    RunORTools --> Evaluate[6軸評価]
    Evaluate --> Output1[結果出力]

    UseCustom --> RunCustom[カスタムアルゴリズム実行]
    RunCustom --> Output2[結果出力]

    Output1 --> End([完了])
    Output2 --> End

    style UseORTools fill:#336688,stroke:#999,stroke-width:2px
    style UseCustom fill:#338844,stroke:#999,stroke-width:2px
```

**判定ロジック**:
1. `OR_Tools_Config`シートが存在するか？
2. B2セルが`True`か？
3. Yes → OR-Tools、No → カスタムアルゴリズム

---

## 3. OR-Toolsエンジン詳細アーキテクチャ

**概要**: OR-Toolsエンジンの内部構造と11種類の制約

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "ShiftGenerator（メインエンジン）"
        SG[CP-SATソルバー統合]
    end

    subgraph "データ層"
        CONFIG[設定データ<br/>Excel読み込み]
        STAFF[スタッフマスタ]
        CONST[制約設定]
    end

    subgraph "制約実装層（ConstraintImplementor）"
        C1[1. 各日に1シフト割り当て]
        C2[2. 勤務日数上下限]
        C3[3. 連続勤務日数制限]
        C4[4. 特定日の休暇指定]
        C5[5. 夜勤後の休暇]
        C6[6. 夜勤回数上下限]
        C7[7. 土日祝均等割り当て]
        C8[8. 希望休暇]
        C9[9. スキルマッチング]
        C10[10. 最低人員配置]
        C11[11. 公平性制約]
    end

    subgraph "目的関数層（ObjectiveFunctionManager）"
        OBJ1[コスト最小化]
        OBJ2[スタッフ満足最大化]
        OBJ3[品質スコア最大化]
        OBJ4[公平性最大化]
    end

    subgraph "評価層（ScenarioEvaluator）"
        EVAL[6軸評価システム]
    end

    subgraph "出力層"
        RESULT[シフト結果Excel]
        REPORT[評価レポート]
    end

    CONFIG --> SG
    STAFF --> SG
    CONST --> SG

    SG --> C1
    SG --> C2
    SG --> C3
    SG --> C4
    SG --> C5
    SG --> C6
    SG --> C7
    SG --> C8
    SG --> C9
    SG --> C10
    SG --> C11

    SG --> OBJ1
    SG --> OBJ2
    SG --> OBJ3
    SG --> OBJ4

    C1 --> EVAL
    C2 --> EVAL
    C3 --> EVAL
    C4 --> EVAL
    C5 --> EVAL
    C6 --> EVAL
    C7 --> EVAL
    C8 --> EVAL
    C9 --> EVAL
    C10 --> EVAL
    C11 --> EVAL

    OBJ1 --> EVAL
    OBJ2 --> EVAL
    OBJ3 --> EVAL
    OBJ4 --> EVAL

    EVAL --> RESULT
    EVAL --> REPORT

    style SG fill:#336688,stroke:#999,stroke-width:3px
    style EVAL fill:#447788,stroke:#999,stroke-width:2px
```

**11種類の制約詳細**:
1. 各日に1シフト割り当て（必須）
2. 月間勤務日数の上下限
3. 連続勤務日数制限（例: 5連勤まで）
4. 特定日の休暇指定
5. 夜勤後は翌日休み
6. 夜勤回数の上下限
7. 土日祝日の均等割り当て
8. 希望休暇の考慮
9. スキルマッチング（資格要件）
10. 最低人員配置（シフトタイプごと）
11. 公平性（経験値差の最小化）

---

# コア機能

## 4. マルチシナリオ生成フロー

**概要**: 5つの最適化戦略で同時にシナリオ生成

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
flowchart TD
    Start([ユーザー指示<br/>「複数シナリオで比較して」]) --> Parse[戦略リスト取得]
    Parse --> Gen1[戦略1: balanced<br/>バランス型]
    Parse --> Gen2[戦略2: cost_optimized<br/>コスト重視]
    Parse --> Gen3[戦略3: quality_focused<br/>品質重視]
    Parse --> Gen4[戦略4: staff_first<br/>スタッフ優先]
    Parse --> Gen5[戦略5: legal_strict<br/>法令厳守]

    Gen1 --> Solve1[CP-SAT最適化]
    Gen2 --> Solve2[CP-SAT最適化]
    Gen3 --> Solve3[CP-SAT最適化]
    Gen4 --> Solve4[CP-SAT最適化]
    Gen5 --> Solve5[CP-SAT最適化]

    Solve1 --> Eval1[6軸評価]
    Solve2 --> Eval2[6軸評価]
    Solve3 --> Eval3[6軸評価]
    Solve4 --> Eval4[6軸評価]
    Solve5 --> Eval5[6軸評価]

    Eval1 --> Compare[シナリオ比較]
    Eval2 --> Compare
    Eval3 --> Compare
    Eval4 --> Compare
    Eval5 --> Compare

    Compare --> Report[比較レポート生成]
    Report --> End([AI報告])

    style Gen1 fill:#4477AA,stroke:#999
    style Gen2 fill:#447788,stroke:#999
    style Gen3 fill:#664488,stroke:#999
    style Gen4 fill:#228833,stroke:#999
    style Gen5 fill:#884444,stroke:#999
```

**使用例**:
```python
result = auto_generate_shift(
    'config.xlsx', 2025, 1,
    strategies=['balanced', 'cost_optimized', 'quality_focused']
)
# → 3シナリオ生成して比較
```

---

## 5. データフロー図（Excel → 出力）

**概要**: データの変換フロー全体像

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
flowchart LR
    subgraph "入力Excel"
        E1[スタッフマスタ]
        E2[制約設定]
        E3[シフトタイプ定義]
        E4[目的関数設定]
        E5[OR_Tools_Config]
    end

    subgraph "内部データ構造"
        I1[StaffConfig<br/>dataclass]
        I2[ConstraintConfig<br/>dataclass]
        I3[ShiftTypeConfig<br/>dataclass]
        I4[ObjectiveWeights<br/>dict]
    end

    subgraph "OR-Tools変数"
        V1[shifts変数<br/>staff × day × shift_type]
        V2[制約式<br/>AddEquality/Inequality]
        V3[目的関数式<br/>Minimize/Maximize]
    end

    subgraph "ソルバー実行"
        S1[CP-SAT Solver]
        S2[最適解探索]
    end

    subgraph "出力変換"
        O1[Solution → DataFrame]
        O2[評価スコア計算]
    end

    subgraph "出力Excel"
        OUT1[シフト表シート]
        OUT2[評価結果シート]
        OUT3[違反ルール詳細シート]
    end

    E1 --> I1
    E2 --> I2
    E3 --> I3
    E4 --> I4

    I1 --> V1
    I2 --> V2
    I3 --> V1
    I4 --> V3

    V1 --> S1
    V2 --> S1
    V3 --> S1

    S1 --> S2
    S2 --> O1
    S2 --> O2

    O1 --> OUT1
    O2 --> OUT2
    O2 --> OUT3

    style S1 fill:#336688,stroke:#999,stroke-width:2px
    style OUT1 fill:#338844,stroke:#999,stroke-width:2px
```

**データ変換の流れ**:
1. Excel読み込み → dataclass変換
2. dataclass → OR-Tools変数・制約式
3. ソルバー実行 → 最適解取得
4. 最適解 → DataFrame変換
5. DataFrame → Excel出力

---

## 6. コンポーネント関係図

**概要**: モジュール間の依存関係

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "ユーザーインターフェース層"
        CLI[CLIインターフェース<br/>Claude Code / Gemini]
    end

    subgraph "アプリケーション層"
        FSA[flexible_system_adapter.py]
        MSG[multi_scenario_generator.py]
    end

    subgraph "エンジン層"
        OSG[shift_generator.py]
        CI[constraint_implementor.py]
        OFM[objective_function_manager.py]
        SE[scenario_evaluator.py]
        CU[constraint_updater.py<br/>★v5.1新規]
    end

    subgraph "コア層"
        EM[excel_manager.py]
        SM[state_manager.py]
        LOG[logger_setup.py]
    end

    subgraph "外部ライブラリ"
        ORTOOLS[Google OR-Tools<br/>CP-SAT]
        PANDAS[pandas]
        OPENPYXL[openpyxl]
    end

    CLI --> FSA
    FSA --> MSG
    FSA --> OSG
    FSA --> CU

    MSG --> OSG
    OSG --> CI
    OSG --> OFM
    OSG --> SE

    CU --> EM

    CI --> EM
    OFM --> EM
    SE --> EM
    OSG --> SM

    EM --> PANDAS
    EM --> OPENPYXL
    OSG --> ORTOOLS
    CI --> ORTOOLS

    style FSA fill:#886633,stroke:#999,stroke-width:3px
    style CU fill:#884444,stroke:#999,stroke-width:2px
    style ORTOOLS fill:#336688,stroke:#999,stroke-width:2px
```

**依存関係の階層**:
1. CLI層 → アプリケーション層
2. アプリケーション層 → エンジン層
3. エンジン層 → コア層
4. コア層 → 外部ライブラリ

---

## 7. 戦略別重み調整マトリクス

**概要**: 5つの最適化戦略の目的関数重み比較

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "5つの最適化戦略"
        S1[balanced<br/>バランス型]
        S2[cost_optimized<br/>コスト重視]
        S3[quality_focused<br/>品質重視]
        S4[staff_first<br/>スタッフ優先]
        S5[legal_strict<br/>法令厳守]
    end

    subgraph "目的関数要素"
        O1[法的遵守<br/>Legal Compliance]
        O2[スタッフ満足<br/>Staff Satisfaction]
        O3[コスト効率<br/>Cost Efficiency]
        O4[品質保証<br/>Quality Assurance]
        O5[公平性<br/>Fairness]
    end

    S1 -->|0.30| O1
    S1 -->|0.25| O2
    S1 -->|0.20| O3
    S1 -->|0.15| O4
    S1 -->|0.10| O5

    S2 -->|0.25| O1
    S2 -->|0.15| O2
    S2 -->|0.40 ⬆️| O3
    S2 -->|0.10| O4
    S2 -->|0.10| O5

    S3 -->|0.25| O1
    S3 -->|0.20| O2
    S3 -->|0.10| O3
    S3 -->|0.35 ⬆️| O4
    S3 -->|0.10| O5

    S4 -->|0.25| O1
    S4 -->|0.40 ⬆️| O2
    S4 -->|0.10| O3
    S4 -->|0.15| O4
    S4 -->|0.10| O5

    S5 -->|0.50 ⬆️| O1
    S5 -->|0.15| O2
    S5 -->|0.15| O3
    S5 -->|0.10| O4
    S5 -->|0.10| O5

    style S1 fill:#4477AA,stroke:#999
    style S2 fill:#447788,stroke:#999
    style S3 fill:#664488,stroke:#999
    style S4 fill:#228833,stroke:#999
    style S5 fill:#884444,stroke:#999
```

**重みマトリクス表**:

| 戦略 | 法的遵守 | スタッフ満足 | コスト効率 | 品質保証 | 公平性 |
|------|---------|------------|-----------|---------|-------|
| balanced | 0.30 | 0.25 | 0.20 | 0.15 | 0.10 |
| cost_optimized | 0.25 | 0.15 | **0.40** ⬆️ | 0.10 | 0.10 |
| quality_focused | 0.25 | 0.20 | 0.10 | **0.35** ⬆️ | 0.10 |
| staff_first | 0.25 | **0.40** ⬆️ | 0.10 | 0.15 | 0.10 |
| legal_strict | **0.50** ⬆️ | 0.15 | 0.15 | 0.10 | 0.10 |

---

## 8. 6軸評価システム

**概要**: 生成されたシフトの品質を6つの軸で評価

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
flowchart TD
    Start([生成されたシフト]) --> Eval1[1. 法的遵守<br/>Legal Compliance]
    Start --> Eval2[2. スタッフ満足<br/>Staff Satisfaction]
    Start --> Eval3[3. コスト効率<br/>Cost Efficiency]
    Start --> Eval4[4. 品質保証<br/>Quality Assurance]
    Start --> Eval5[5. 公平性<br/>Fairness]
    Start --> Eval6[6. 堅牢性<br/>Robustness]

    Eval1 --> Score1[労働基準法違反チェック<br/>スコア: 0-100]
    Eval2 --> Score2[希望シフト充足率<br/>スコア: 0-100]
    Eval3 --> Score3[人件費計算<br/>スコア: 0-100]
    Eval4 --> Score4[スキルマッチング率<br/>スコア: 0-100]
    Eval5 --> Score5[勤務日数の標準偏差<br/>スコア: 0-100]
    Eval6 --> Score6[制約違反数<br/>スコア: 0-100]

    Score1 --> Aggregate[総合スコア計算<br/>重み付け平均]
    Score2 --> Aggregate
    Score3 --> Aggregate
    Score4 --> Aggregate
    Score5 --> Aggregate
    Score6 --> Aggregate

    Aggregate --> Report[評価レポート生成]

    style Eval1 fill:#884444,stroke:#999
    style Eval2 fill:#228833,stroke:#999
    style Eval3 fill:#447788,stroke:#999
    style Eval4 fill:#664488,stroke:#999
    style Eval5 fill:#886633,stroke:#999
    style Eval6 fill:#4477AA,stroke:#999
```

**6軸評価詳細**:
1. **法的遵守**: 労働基準法違反の有無（週40時間、月60時間残業など）
2. **スタッフ満足**: 希望休暇・希望シフトの充足率
3. **コスト効率**: 人件費の最小化（正職員/パート比率最適化）
4. **品質保証**: スキルマッチング率、資格要件の充足
5. **公平性**: 勤務日数・夜勤回数の偏り最小化
6. **堅牢性**: 制約違反数（少ないほど良い）

---

# 運用・テスト

## 9. テストアーキテクチャ

**概要**: ユニットテスト、統合テストの構成

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "テスト環境"
        UT[ユニットテスト<br/>pytest]
        IT[統合テスト<br/>E2Eテスト]
        PT[パフォーマンステスト]
    end

    subgraph "テスト対象"
        T1[excel_manager.py]
        T2[constraint_implementor.py]
        T3[shift_generator.py]
        T4[scenario_evaluator.py]
        T5[constraint_updater.py<br/>★v5.1]
    end

    subgraph "テストデータ"
        TD1[サンプル施設Excel]
        TD2[モックデータ]
    end

    subgraph "検証項目"
        V1[制約充足性]
        V2[最適解の妥当性]
        V3[パフォーマンス<br/>30秒以内]
        V4[エラーハンドリング]
    end

    UT --> T1
    UT --> T2
    UT --> T5

    IT --> T3
    IT --> T4

    PT --> T3

    TD1 --> IT
    TD2 --> UT

    T1 --> V4
    T2 --> V1
    T3 --> V2
    T3 --> V3
    T4 --> V2
    T5 --> V4

    style UT fill:#336688,stroke:#999
    style IT fill:#338844,stroke:#999
    style PT fill:#664488,stroke:#999
```

**テスト戦略**:
- **ユニットテスト**: 各モジュールの関数単位でテスト
- **統合テスト**: Excel入力→シフト出力の完全フロー
- **パフォーマンステスト**: 30秒以内の完了を保証

---

## 10. デプロイメント構成（シンプル版）

**概要**: ローカル実行とサーバー実行の構成

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "ローカル環境"
        L1[Windows PC]
        L2[Python 3.8+]
        L3[Excel 2016+]
        L4[Claude Code CLI]
    end

    subgraph "サーバー環境（オプション）"
        S1[Linuxサーバー]
        S2[Python 3.8+]
        S3[Webインターフェース]
    end

    subgraph "共通コンポーネント"
        C1[OR-Tools]
        C2[pandas]
        C3[openpyxl]
    end

    L1 --> L2
    L2 --> L4
    L2 --> C1
    L2 --> C2
    L2 --> C3
    L3 --> L1

    S1 --> S2
    S2 --> S3
    S2 --> C1
    S2 --> C2
    S2 --> C3

    style L1 fill:#336688,stroke:#999
    style S1 fill:#338844,stroke:#999
```

**デプロイ方法**:
- **ローカル**: Windows PC + Python + Claude Code
- **サーバー**: Linux + Python + Webインターフェース（将来実装）

---

# AI連携

## 11. 対話ループフロー（AI連携）

**概要**: ユーザーとAIの対話によるシフト改善フロー

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','actorTextColor':'#fff','labelTextColor':'#fff','loopTextColor':'#fff','activationBorderColor':'#aaa','actorBorder':'#aaa','actorLineColor':'#aaa','signalColor':'#aaa','signalTextColor':'#fff'}}}%%
sequenceDiagram
    actor U as ユーザー
    participant AI as AI Agent<br/>(Claude Code)
    participant PY as Pythonシステム
    participant EX as Excel

    U->>AI: 「来月のシフト作成して」
    AI->>EX: Excel読み込み
    EX-->>AI: 設定データ
    AI->>PY: auto_generate_shift()実行
    PY->>PY: OR-Tools最適化
    PY-->>AI: シフト結果＋評価スコア
    AI->>AI: 日本語レポート生成
    AI-->>U: 「シフト生成完了<br/>法的遵守100%、スタッフ満足78点」

    U->>AI: 「山田さんは28日休みにして」
    AI->>EX: スタッフマスタ確認
    EX-->>AI: 山田太郎(S005)、山田花子(S012)
    AI-->>U: 「山田太郎さんと山田花子さんがいます<br/>どちらですか？」

    U->>AI: 「太郎です」
    AI->>PY: add_dayoff_constraint('config.xlsx', 'S005', '2025-01-28')
    PY->>EX: 制約追加
    EX-->>PY: 成功
    PY-->>AI: True
    AI-->>U: 「制約を追加しました」

    AI->>PY: auto_generate_shift()再実行
    PY->>PY: OR-Tools最適化
    PY-->>AI: 新しいシフト結果
    AI-->>U: 「再生成完了<br/>山田太郎さんは28日休みです」

    U->>AI: 「OK、これで確定して」
    AI-->>U: 「シフトを確定しました<br/>sunshine_care_202501_shift.xlsx」
```

**対話フロー**:
1. ユーザーが自然言語で指示
2. AIが理解してPython実行
3. 結果を日本語で報告
4. ユーザーが修正依頼
5. AIが制約追加して再生成
6. 繰り返し改善

---

## 12. AI-システム責任分担図

**概要**: AI層とPythonシステム層の責任分界

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph LR
    subgraph "AI層の責任（Claude Code / Gemini）"
        AI1[自然言語理解]
        AI2[対話管理]
        AI3[曖昧性解決]
        AI4[結果の日本語説明]
        AI5[エラーメッセージ翻訳]
    end

    subgraph "Pythonシステム層の責任"
        PY1[シフト生成<br/>OR-Tools実行]
        PY2[制約実装<br/>11種類]
        PY3[評価スコア計算<br/>6軸]
        PY4[Excel読み書き]
        PY5[エラーハンドリング]
    end

    subgraph "共有責任"
        SH1[Excel制約追加<br/>AIが指示→Pythonが実行]
        SH2[レポート生成<br/>Pythonが計算→AIが説明]
    end

    AI1 --> SH1
    SH1 --> PY4

    PY3 --> SH2
    SH2 --> AI4

    style AI1 fill:#884444,stroke:#999
    style AI2 fill:#884444,stroke:#999
    style AI3 fill:#884444,stroke:#999
    style AI4 fill:#884444,stroke:#999
    style AI5 fill:#884444,stroke:#999

    style PY1 fill:#336688,stroke:#999
    style PY2 fill:#336688,stroke:#999
    style PY3 fill:#336688,stroke:#999
    style PY4 fill:#336688,stroke:#999
    style PY5 fill:#336688,stroke:#999

    style SH1 fill:#664488,stroke:#999
    style SH2 fill:#664488,stroke:#999
```

**責任分担**:

| 責任 | AI層 | Python層 |
|------|------|----------|
| 自然言語理解 | ✅ | - |
| 対話管理 | ✅ | - |
| 曖昧性解決 | ✅ | - |
| シフト生成 | - | ✅ |
| 制約実装 | - | ✅ |
| 評価計算 | - | ✅ |
| Excel操作 | ✅ (指示) | ✅ (実行) |
| レポート生成 | ✅ (説明) | ✅ (計算) |

---

# モード管理 v5.1

## 13. モードベースアクセス制御フロー

**概要**: Production/Test/Debugモードによる実行制御

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
flowchart TD
    Start([AI実行開始]) --> CheckMode{現在のモード確認<br/>.ai_mode}

    CheckMode -->|production| ProdMode[🔴 本番モード]
    CheckMode -->|test| TestMode[🟡 テストモード]
    CheckMode -->|debug| DebugMode[🟢 デバッグモード]

    ProdMode --> ClassifyReq{要求タイプ判定}
    TestMode --> ClassifyReq
    DebugMode --> ClassifyReq

    ClassifyReq -->|ホワイトリスト関数| WhitelistCheck{権限チェック}
    ClassifyReq -->|新規スクリプト| NewScriptCheck{権限チェック}
    ClassifyReq -->|OR-Tools直接| DirectORCheck{権限チェック}

    WhitelistCheck -->|production| AllowWL[✅ 実行許可]
    WhitelistCheck -->|test| AllowWL
    WhitelistCheck -->|debug| AllowWL

    NewScriptCheck -->|production| DenyNew[❌ 実行拒否<br/>本番モードでは禁止]
    NewScriptCheck -->|test| ConfirmNew[⚠️ ユーザー確認必須<br/>「この新規スクリプトを実行しますか？」]
    NewScriptCheck -->|debug| AllowNew[✅ 自由に実行]

    DirectORCheck -->|production| DenyOR[❌ 実行拒否<br/>auto_generate_shift()を使用]
    DirectORCheck -->|test| ConfirmOR[⚠️ ユーザー確認必須]
    DirectORCheck -->|debug| AllowOR[✅ 自由に実行]

    AllowWL --> Execute[スクリプト実行]
    AllowNew --> Execute
    AllowOR --> Execute

    ConfirmNew -->|Yes| Execute
    ConfirmNew -->|No| Cancel[❌ 実行キャンセル]

    ConfirmOR -->|Yes| Execute
    ConfirmOR -->|No| Cancel

    DenyNew --> Suggest[代替方法提案<br/>「テストモードに切り替えてください」]
    DenyOR --> Suggest

    Execute --> End([完了])
    Cancel --> End
    Suggest --> End

    style ProdMode fill:#884444,stroke:#999,stroke-width:3px
    style TestMode fill:#886633,stroke:#999,stroke-width:3px
    style DebugMode fill:#338844,stroke:#999,stroke-width:3px
```

**モード別動作**:
- **🔴 Production**: ホワイトリストのみ、新規スクリプト禁止
- **🟡 Test**: ユーザー確認で新規スクリプト許可
- **🟢 Debug**: すべて許可、開発用

---

## 14. モード別権限マトリクス

**概要**: 各モードでの操作権限一覧

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "操作タイプ"
        OP1[ホワイトリスト関数<br/>auto_generate_shift等]
        OP2[新規スクリプト作成]
        OP3[OR-Tools直接使用]
        OP4[Excel直接操作<br/>openpyxl]
        OP5[ファイルシステム操作]
    end

    subgraph "Production（本番）"
        P1[✅ 許可]
        P2[❌ 禁止]
        P3[❌ 禁止]
        P4[❌ 禁止]
        P5[❌ 禁止]
    end

    subgraph "Test（テスト）"
        T1[✅ 許可]
        T2[⚠️ 確認必須]
        T3[⚠️ 確認必須]
        T4[⚠️ 確認必須]
        T5[⚠️ 確認必須]
    end

    subgraph "Debug（デバッグ）"
        D1[✅ 許可]
        D2[✅ 許可]
        D3[✅ 許可]
        D4[✅ 許可]
        D5[✅ 許可]
    end

    OP1 --> P1
    OP1 --> T1
    OP1 --> D1

    OP2 --> P2
    OP2 --> T2
    OP2 --> D2

    OP3 --> P3
    OP3 --> T3
    OP3 --> D3

    OP4 --> P4
    OP4 --> T4
    OP4 --> D4

    OP5 --> P5
    OP5 --> T5
    OP5 --> D5

    style P1 fill:#338844,stroke:#999
    style P2 fill:#884444,stroke:#999
    style P3 fill:#884444,stroke:#999
    style P4 fill:#884444,stroke:#999
    style P5 fill:#884444,stroke:#999

    style T1 fill:#338844,stroke:#999
    style T2 fill:#886633,stroke:#999
    style T3 fill:#886633,stroke:#999
    style T4 fill:#886633,stroke:#999
    style T5 fill:#886633,stroke:#999

    style D1 fill:#338844,stroke:#999
    style D2 fill:#338844,stroke:#999
    style D3 fill:#338844,stroke:#999
    style D4 fill:#338844,stroke:#999
    style D5 fill:#338844,stroke:#999
```

**権限マトリクス表**:

| 操作タイプ | Production | Test | Debug |
|-----------|-----------|------|-------|
| ホワイトリスト関数 | ✅ | ✅ | ✅ |
| 新規スクリプト作成 | ❌ | ⚠️ | ✅ |
| OR-Tools直接使用 | ❌ | ⚠️ | ✅ |
| Excel直接操作 | ❌ | ⚠️ | ✅ |
| ファイルシステム操作 | ❌ | ⚠️ | ✅ |

**凡例**:
- ✅ 無条件で許可
- ⚠️ ユーザー確認が必要
- ❌ 実行拒否

---

## 15. モード切り替えシーケンス

**概要**: モード切り替えの実行シーケンス詳細

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','actorTextColor':'#fff','labelTextColor':'#fff','loopTextColor':'#fff','activationBorderColor':'#aaa','actorBorder':'#aaa','actorLineColor':'#aaa','signalColor':'#aaa','signalTextColor':'#fff'}}}%%
sequenceDiagram
    actor U as ユーザー
    participant CLI as コマンドライン
    participant MM as AIModeManager
    participant CFG as .ai_modeファイル
    participant AI as AI Agent
    participant PY as Pythonシステム

    rect rgb(136, 68, 68)
    Note over U,CFG: シナリオ1: コマンドライン切り替え
    U->>CLI: python ai_mode_manager.py set production
    CLI->>MM: set_mode(production)
    MM->>CFG: 設定書き込み<br/>mode: production
    CFG-->>MM: 成功
    MM-->>CLI: モード切り替え完了
    CLI-->>U: ✅ Production mode enabled
    end

    rect rgb(51, 136, 68)
    Note over U,PY: シナリオ2: 自然言語切り替え
    U->>AI: 「本番モードでシフト作成して」
    AI->>MM: get_current_mode()
    MM->>CFG: 設定読み込み
    CFG-->>MM: mode: test
    MM-->>AI: ExecutionMode.TEST
    AI->>MM: set_mode(production)
    MM->>CFG: mode: production
    CFG-->>MM: 成功
    MM-->>AI: 切り替え完了
    AI->>PY: auto_generate_shift()
    PY-->>AI: シフト結果
    AI-->>U: 「本番モードでシフト生成完了」
    end

    rect rgb(68, 119, 170)
    Note over U,PY: シナリオ3: 権限エラー時の対応
    U->>AI: 「新しい制約タイプを試したい」
    AI->>MM: get_current_mode()
    MM-->>AI: ExecutionMode.PRODUCTION
    AI->>MM: is_allowed('new_script')
    MM-->>AI: (False, "本番モードでは禁止")
    AI-->>U: ❌ 本番モードでは新規スクリプト作成できません<br/>テストモードに切り替えてください
    U->>AI: 「テストモードに切り替えて」
    AI->>MM: set_mode(test)
    MM->>CFG: mode: test
    CFG-->>MM: 成功
    MM-->>AI: 切り替え完了
    AI-->>U: ✅ テストモードに切り替えました<br/>新規スクリプトが実行可能です
    end
```

**モード切り替え方法**:
1. **コマンドライン**: `python ai_mode_manager.py set <mode>`
2. **自然言語**: 「本番モードで実行して」
3. **環境変数**: `export AI_EXECUTION_MODE=debug`

---

## 16. 全体アーキテクチャ（モード統合版）

**概要**: モード管理層を含む完全なシステム構成

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryTextColor':'#fff','secondaryTextColor':'#fff','tertiaryTextColor':'#fff','textColor':'#fff','primaryBorderColor':'#aaa','secondaryBorderColor':'#aaa','lineColor':'#aaa','edgeLabelBackground':'#333'}}}%%
graph TB
    subgraph "ユーザー層"
        U[介護施設管理者]
    end

    subgraph "AI対話層"
        AI[AI Agent<br/>Claude Code / Gemini]
    end

    subgraph "モード管理層 ★v5.1"
        MM[ai_mode_manager.py]
        CFG[.ai_mode設定ファイル]
    end

    subgraph "実行制御"
        PermCheck{権限チェック}
        Prod[🔴 本番モード実行]
        Test[🟡 テストモード実行]
        Debug[🟢 デバッグモード実行]
    end

    subgraph "アプリケーション層"
        FSA[FlexibleSystemAdapter]
        MSG[MultiScenarioGenerator]
        CU[ConstraintUpdater ★v5.1]
    end

    subgraph "エンジン層"
        OSG[OR-Tools ShiftGenerator]
        SE[ScenarioEvaluator]
    end

    subgraph "データ層"
        EX[Excel設定ファイル]
        OUT[シフト結果Excel]
    end

    U <-->|自然言語対話| AI
    AI --> MM
    MM <--> CFG

    AI --> PermCheck
    PermCheck -->|production| Prod
    PermCheck -->|test| Test
    PermCheck -->|debug| Debug

    Prod --> WL[ホワイトリスト関数]
    Test --> WL
    Test --> NEW[新規スクリプト<br/>確認後]
    Debug --> WL
    Debug --> NEW
    Debug --> OR[OR-Tools直接]

    WL --> FSA
    WL --> CU
    NEW --> FSA
    OR --> OSG

    FSA --> MSG
    FSA --> OSG
    MSG --> OSG

    CU --> EX
    OSG --> SE
    EX --> OSG
    SE --> OUT

    OUT --> AI
    AI --> U

    style MM fill:#884444,stroke:#999,stroke-width:3px
    style CFG fill:#884444,stroke:#999,stroke-width:2px
    style Prod fill:#884444,stroke:#999,stroke-width:2px
    style Test fill:#886633,stroke:#999,stroke-width:2px
    style Debug fill:#338844,stroke:#999,stroke-width:2px
    style CU fill:#664488,stroke:#999,stroke-width:2px
```

**統合アーキテクチャのポイント**:
1. **モード管理層**がAI実行を制御
2. **3つのモード**で安全性とフレキシビリティを両立
3. **Phase 1 (v5.1)**でConstraintUpdater追加
4. **ホワイトリスト**で本番環境の安全性確保

---

## 📝 まとめ

### システムの特徴

1. **AI駆動**: 自然言語で指示、AIがPython実行
2. **2つのエンジン**: OR-Tools（高度） / カスタム（軽量）
3. **5つの戦略**: balanced, cost_optimized, quality_focused, staff_first, legal_strict
4. **6軸評価**: 法的遵守、スタッフ満足、コスト効率、品質、公平性、堅牢性
5. **11種類の制約**: 労働基準法から公平性まで包括的に対応
6. **モード管理**: Production/Test/Debugで安全性確保

### v5.1での追加機能

- **ConstraintUpdater**: Excel制約を動的追加（5関数）
- **モード管理システム**: AI実行の安全性制御（3モード）
- **対話ループ**: 繰り返し改善フロー

### 次のステップ

- **Phase 2**: 自然言語パーサー実装
- **Phase 3**: 対話状態管理実装

---

**ドキュメント作成**: Claude Code
**バージョン**: v5.1
**最終更新**: 2025-10-01
