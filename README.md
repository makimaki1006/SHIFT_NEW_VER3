# Shift-Suite

Shift-Suite is a collection of utilities for analysing and visualising Excel
shift schedules. It offers both a graphical interface built with Streamlit
and a lightweight command line tool for batch execution.

## Main modules

- **`app.py`** - Launches the Streamlit based GUI. The application guides you
  through uploading an Excel file, selecting sheets and running various
  analyses such as heatmap generation and shortage detection.
- **`cli.py`** - Provides a command line interface for running a subset of the
  analysis pipeline without the GUI. It ingests an Excel file, builds a
  heatmap, runs shortage analysis and summarises the results.

The `shift_suite/tasks` package holds the analysis modules listed below. They
are automatically imported by `shift_suite/__init__.py`, so you can simply
`import shift_suite` and access them as attributes (e.g. `shift_suite.heatmap`).

- **`heatmap`** - Generates time-slot heatmaps and calculates required staff
  numbers from shift records.
- **`shortage`** - Computes staff shortages based on heatmap data and outputs
  summary spreadsheets.
- **`build_stats`** - Aggregates KPIs and produces overall and monthly
  statistics.
- **`forecast`** - Builds demand series and forecasts future staffing needs via
  time-series models. Each run appends the selected model and MAPE to
  `forecast_history.csv` and holiday dates can be passed as exogenous inputs.
- **`fairness`** - Evaluates fairness in shift allocation across staff members.
- **`rl`** - Experimental reinforcement-learning module for generating
  optimised rosters.
- **`hire_plan`** - Estimates the number of hires required to meet forecast
  demand.
- **`h2hire`** - Converts shortage hours into required FTE hires.
- **`cluster`** - Groups staff automatically by shift pattern.
- **`fatigue`** - Trains a simple model and outputs fatigue scores per staff.
- **`skill_nmf`** - Estimates a latent skill matrix using non-negative matrix factorisation.
- **`anomaly`** - Detects irregular shift patterns via IsolationForest.
- **`cost_benefit`** - Simulates labour costs and hiring scenarios.
- **`ppt`** - Builds a PowerPoint report summarising heatmaps, shortage metrics
  and cost simulations (requires the optional `python-pptx` library).
- **`leave_analyzer`** - Summarises paid and requested leave days.
- **`cli_bridge`** - Lightweight CLI for `leave_analyzer` based on CSV input.

The GUI caches the uploaded workbook using `load_excelfile_cached()` with
`st.cache_resource`, as `pd.ExcelFile` objects cannot be pickled.

## Usage

1. Install dependencies (requires Python 3.12 or later):

   ```bash
   pip install -r requirements.txt
   ```

   The `requirements.txt` file pins `scikit-learn` to `1.4.1.post1` for
   compatibility with Python 3.12.
   It also installs `streamlit-plotly-events` so the leave analysis charts
   can respond to clicks and selections.

2. To use the GUI, run:

   ```bash
   streamlit run app.py
   ```

   Follow the on-screen instructions to upload your shift spreadsheet and
   execute the desired analyses. Separate upload fields are provided for
   global and local holiday calendars if you wish to factor them into the
   shortage analysis and forecasts.

3. To use the CLI, run:

   ```bash
   python cli.py <excel.xlsx> <out_dir> [--slot MIN] [--header ROW] [--zip] \
       [--holidays-global FILE] [--holidays-local FILE] [--safety-factor NUM]
   ```

   - `<excel.xlsx>`: path to the source Excel file
   - `<out_dir>`: directory where results will be written
   - `--slot`: time slot length in minutes (default: 30)
   - `--header`: header row number in the shift sheets (default: 2)
   - `--zip`: optionally compress the output directory
   - `--holidays-global`: CSV/JSON with nationally observed holidays
   - `--holidays-local`: CSV/JSON with site-specific holidays
   - `--safety-factor`: multiplier applied to shortage hours when automatically
     generating a hire plan (default: 1.0)

4. Run analyses directly on a CSV file using the module entry point:

   ```bash
   python -m shift_suite.tasks.cli_bridge --analysis <type> <csv> --out <dir>
   ```

   Available analysis types are `leave`, `rest`, `work`, `attendance`,
   `lowstaff`, `score` and `all`. The `leave` option mirrors the previous
   behaviour and outputs `leave_analysis.csv`. When using `lowstaff`, you
   may optionally pass `--threshold` to set the staff-count threshold (either
   a value or quantile).

   Example: generate combined scores with

   ```bash
   python -m shift_suite.tasks.cli_bridge --analysis score shifts.csv --out results
   ```

   Example: analyse low staff load with a custom threshold

   ```bash
   python -m shift_suite.tasks.cli_bridge --analysis lowstaff --threshold 0.2 shifts.csv --out results
   ```

The analysis code lives under the `shift_suite/tasks` package. Results are
written to the specified output directory or displayed directly in the GUI.

### Dash dashboard

`dash_app.py` exposes the multi-tenant dashboard used to review batch analysis outputs. To inspect a scenario:

1. Run `python dash_app.py` and open the served URL in a browser (default http://127.0.0.1:8055).
2. Upload the zipped analysis results (for example, an archive that contains the `out_*` directories). The app automatically ingests heatmaps, shortage metrics, forecast files, gap reports, blueprint/Mind Reader JSON, and logic analysis artefacts when present.
3. **Select a color scheme** (Phase 3-5 feature): Choose from three heatmap color gradients:
   - **モダンブルー（Modern Blue）** - Default blue gradient
   - **プロフェッショナル（Professional）** - Monochrome gray gradient
   - **バイブラント（Vibrant）** - Vivid purple gradient
4. Navigate across the tabs. In addition to **Overview** / **Heatmap** / **Shortage**, the dashboard includes **Forecast**, **Gap**, **Blueprint**, **Logic**, and **AI** pages. Tabs that lack the required artefacts display placeholders so you can track migration progress without breaking the flow.

The color scheme selection applies to heatmap visualizations in the Heatmap tab, allowing users to customize the visualization based on personal preference or accessibility needs.

Tabs that rely on optional artefacts (such as Mind Reader outputs) surface guidance when the requisite JSON or parquet files are missing, enabling incremental adoption.

> **Session behaviour note**
> The 18 navigation tabs are rendered as part of the static layout. Each browser session maintains its own scenario payload, so uploading a ZIP in one session does not alter the data shown in another session. Color scheme preferences are also session-specific.

### Additional dependencies

Some modules require extra libraries such as `prophet` for forecasting or
`stable-baselines3` and `torch` for reinforcement learning. PowerPoint report
generation uses `python-pptx`, which is optional. Install these via
`pip install -r requirements.txt` before running `app.py` or the CLIs if you
need the related features.

### Reinforcement learning

`learn_roster` optionally loads a saved PPO model. If the model cannot
be deserialised, an error is logged and the function returns `None`
instead of raising an exception.

### Example output

Running the bridge command on a CSV with `staff`, `ds` (timestamp) and
`holiday_type` columns produces a CSV like the following:

```text
date,staff,leave_type,leave_day_flag
2024-04-01,Alice,希望休,1
2024-04-01,Bob,有給,1
```

The GUI displays the same data interactively under the **Leave Analysis** tab.

### 勤務予定人数と希望休取得者数 chart

Within the **Leave Analysis** tab there is a line chart labelled “勤務予定人数と希望休取得者数”.
It plots the total scheduled staff, the number requesting leave and the
remaining staff available each day. This chart is generated by the
`display_leave_analysis_tab` function in `app.py`.

### Leave concentration graphs

The tab also shows line charts for days where leave requests exceed the
concentration threshold. Hovering over the points reveals the staff names who
requested leave. A second chart plots the share of requesting staff
(`leave_applicants_count / total_staff`) for those days.

You can click or lasso points on this chart to select specific dates. Multiple
dates accumulate across clicks, and the selected staff members are listed below,
together with a bar chart showing how frequently each person appears within the
chosen range. Use the **選択をクリア** button to reset the selection.

### Shortage -> Hire plan workflow

After `shortage_role.xlsx` is generated, the application automatically runs
`h2hire.build_hire_plan` to convert shortage hours into required FTE counts.
The *Safety factor* slider is also applied here (default `1.0`). The resulting `hire_plan.xlsx` is stored in the same output folder and
the **Shortage** tab displays these FTE numbers per role.

If you select the optional **Hire plan** module, the application instead calls
`tasks.hire_plan.build_hire_plan`. This function honours the current value of
the *Safety factor* slider found under **Cost & Hire Parameters** (range
`0.00–2.00`, default `1.10`).

The CLI additionally runs a cost/benefit simulation once the hire plan has
been created. `analyze_cost_benefit(out_dir)` writes `cost_benefit.xlsx`
to the same folder. You can customise the calculation with optional
parameters:

- `wage_direct` - hourly cost of direct employees (default `1500`)
- `wage_temp` - hourly cost for temporary staff (default `2200`)
- `hiring_cost_once` - one-time cost per hire (default `180000`)
- `penalty_per_lack_h` - penalty per uncovered hour (default `4000`)
- `safety_factor` - multiplier applied when running
`tasks.hire_plan.build_hire_plan` (default `1.10`). This same value is passed to
`h2hire.build_hire_plan` when shortage results are converted automatically.
  The value can also be set via the `--safety-factor` CLI option.

If a `leave_analysis.csv` is also present in the output folder you can call
`merge_shortage_leave(out_dir)` to create `shortage_leave.xlsx`. This file
combines the per-slot shortage counts with daily leave applicants and adds a
`net_shortage` column. The Streamlit dashboard automatically visualises this
table under the **Shortage** tab.

