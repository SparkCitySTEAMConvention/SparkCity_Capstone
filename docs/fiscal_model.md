# Fiscal predictive model and grading evidence

Run `notebooks/Hakeem_fiscal_model.ipynb` after `uv sync --dev`, using the project
`.venv` kernel and Java 17. The notebook reads the pinned, completed Day 4/3 lineage.
No new dependencies or source regeneration are required. Database publication is off
by default. Each run writes `data/processed/fiscal_model/<run>`; keep the whole directory.

## Prediction contract

Predict next-calendar-day **mean revenue and expense per observation**, after the
previous day closes. Fiscal sensor observations are roughly 300 hours apart, so
individual sensor lags are not daily measurements. Spark instead builds a daily panel
from all validated observations. These means are not city totals or convention receipts.

For the pinned data, the last observed day is January 10, 2026; the next unobserved
target is January 11, 2026. It is not a forecast for today's date or April 7–9, 2027.
Do not recursively extend a one-day model to the convention dates and imply that
the longer horizon has been validated. The separately modeled convention costs and
visitor spending remain assumptions, not outputs calibrated by this predictor.

## Rubric mapping

The technical pipeline/persistence evidence addresses the 60% implementation category;
model evaluation, diagnostics and charts address the 25% analytics category; the notebook,
model card, instructions and presentation outline address the 15% documentation category.
These are evidence mappings, not a promised grade.

| Criterion | Concrete evidence | Boundary |
|---|---|---|
| Code quality / PySpark | `fiscal_forecast.py`: named, testable functions; projected Parquet input; shared validator; cached reuse with `finally` unpersist; PySpark ML Pipeline/RandomForest | Small daily ridge regressions use NumPy with saved training-only scalers; Spark is not forced onto every 375-row operation |
| Robust pipeline | Source manifest/hash checks, row accounting, typed timestamps, finite values, duplicate/null checks, missing-calendar handling | Does not modify the shared validator or silently repair invalid source data |
| Performance | Collect only 375 daily rows from 36,000 observations; measured aggregation, fitting/evaluation and saved-inference runtimes | Single-machine timings, not cold-start comparisons or scalability claims |
| Database persistence | `003_fiscal_forecasts.sql`, `fiscal_forecast_store.py`: versioned model/metric metadata, prediction keys/checks, atomic publication, safe retries | Optional; requires isolated testing and S2 permissions before deployment |
| Analysis depth | Baselines plus regularized regression and Spark forest; four chronological partitions; same-date RMSE/MAE/R²/bias | Synthetic, one seasonal cycle; within-project backtest, not external real-world validation |
| Visualizations | Actual/predicted series with residual bands, baseline RMSE comparisons, residual histograms | Model selection happens before test charts are inspected |
| Anomaly detection | Outside-band review candidates plus earlier prior-only MAD analysis | No labeled incidents; no claimed precision/recall or false-positive rate |
| Reproducibility | Pinned source, fixed forest seed/settings, JSON/scaler/model state, inference round-trip checks, manifests and file hashes | Retain Spark model subdirectories with the JSON |
| Presentation | Generated `model_card.md`, split audit, metrics, model contract and this architecture explanation | State negative/weak results honestly; a baseline may win |

## Architecture

```text
Day 4 manifest → verified Day 3 fiscal Parquet
    → Spark validation + daily aggregation → calendar-aware lag features
    → training → validation model selection → residual calibration → held-out test
    → model files + metrics + prediction exports + completion manifest
    → optional transactional PostgreSQL publication → future Fiscal Impact page
```

The dashboard shell is not modified by this modeling task. Proposed page sections:
historical fiscal evidence; next-day model/backtest; forecast review candidates;
separately labeled convention scenarios; data freshness, provenance and limitations.

## Leakage controls and evaluation

- Calendar split: 60% train, 15% validation, 10% calibration, 15% test. Boundaries are
  fixed before excluding incomplete histories. With current data: 197/56/37/57 usable
  target dates; 28 warm-up days excluded from training.
- Features: prior revenue/expense at lags 1 and 7; prior 7-/28-day means; target weekday.
  No target-day financial values, generator multipliers or future occupancy/weather.
- Ridge centers/scales use training rows only. Forest settings are fixed at 30 trees,
  depth 3, minimum leaf size 10, seed 42. Ridge penalties are fixed at 1, 10 and 100.
- Four baselines: training mean, yesterday, same weekday last week, trailing seven days.
  Lowest validation RMSE wins, including baselines. No refitting after selection.
- Test is rolling one-day-ahead: earlier test actuals become legitimate lag inputs after
  those days close. It is not a 57-day forecast made at the test boundary.
- Bands use the ordered absolute calibration residual at ceil((n+1) × 0.90), capped at n.
  Calibration is separate from model selection. Temporal dependence and distribution
  shifts prevent a guaranteed 90% coverage claim; actual test coverage is reported.
- Nonnegative clipping is applied identically during selection, calibration, testing
  and inference. There are no post-test hyperparameter changes or event-causal claims.

## Optional database deployment

The notebook's `APPLY_DATABASE=False` and `INITIALIZE_FORECAST_TABLES=False` are safe
defaults. After approval, first initialization uses `sql/003_fiscal_forecasts.sql` in
`sparkcity_analytics_hakeem`. Credentials stay in the environment or ignored `secrets/.env`;
the existing shared helper enforces SSL. Do not copy credentials into notebooks.

One immutable run holds model metadata and evaluation metrics. Prediction grain is
run × target × target date × prediction kind. The primary key supports that retrieval;
date and finite-value checks enforce the one-day contract. Identical run retries are
no-ops; changed content with the same ID is rejected. The publication pointer and all
rows commit together. An old retry does not roll the active pointer back. No raw table
or previous model version is overwritten.

JSON metadata is persisted in PostgreSQL; Spark model binaries remain in the run directory
and need durable deployment storage before remote inference. The app should use a
separate read-only account. Local manifests do not imply successful S2 publication;
an optional publication receipt records that action separately.

## Suggested presentation

1. State the target, horizon and distinction from convention scenarios.
2. Show validation/aggregation row counts and the chronological split.
3. Compare the selected model with baselines on the same held-out dates.
4. Show band coverage and one review candidate; explain missing incident labels.
5. Demonstrate saved-model inference and describe atomic database publication.
6. Close with limits: synthetic data, uncertain units, limited history and no validated
   April 2027 or causal convention-effect forecast.

## Verified results — September 17, 2026

Final local run: `data/processed/fiscal_model/20260917T195400718587Z`.
All notebook code cells executed, saved inference matched exported predictions, and
16 exported-file hashes plus the Spark model-directory hash were verified.

| Target | Validation-selected model | Test RMSE | Test R² | Strongest baseline observed on test |
|---|---|---|---|---|
| Revenue | Ridge, penalty 100 | 28.939 | -0.377 | Trailing seven-day mean, RMSE 25.525 |
| Expense | Spark random forest | 7.010 | -0.032 | Training mean, RMSE 6.910 |

Values are source units per observation. Neither selected model outperformed the strongest
test baseline; neither has positive held-out R². The model-selection decision was not
changed after inspecting test results. Revenue predictions also had a positive bias of
21.365 source units. This is an experimental, reproducible model evaluation—not an
operational forecast recommendation. More representative data and a fresh evaluation
period are needed before further model changes can be evaluated independently.

Calibration-residual bands covered 98.2% of revenue and 94.7% of expense test dates,
but their widths matter: approximately 115.84 and 27.07 source units respectively.
High coverage alone does not establish useful predictive skill.

On this machine, Spark validation/aggregation processed 36,000 records into 375 daily
rows in about 5.6 seconds; fitting, selection, calibration and test evaluation took
about 7 seconds. Exact measurements and configuration are in `performance.json`.

Full regression suite: **109 passed**, including isolated Docker PostgreSQL tests for
schema creation, actual prediction/model read-back, identical retries, changed-content
rejection and atomic rollback. The disposable container was stopped and removed.
No S2 connection, raw-data update, shared-dashboard edit or external notification occurred.
