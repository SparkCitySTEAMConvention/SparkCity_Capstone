# Day 3 instructor alignment

Compared `day3_stuff.txt` with `notebooks/Hakeem_day3.ipynb`. The instructor file is a teaching scaffold, with incomplete examples, invalid loader syntax and commented-out writes; its learning objectives guide this revision, not literal code copying.

| Instructor topic | Revised implementation |
|---|---|
| Temporal patterns | Existing daily/hourly/weekday profiles plus year-month, weekend and peak/off-peak reports with counts |
| Seasonal decomposition | Explicit additive weekly decomposition of uninterrupted daily means, minimum 28 days; retrospective only |
| Pattern anomalies | Daily mean versus prior same-weekday observations, minimum four in previous eight weekly positions; review flags and assessed counts |
| Cross-sensor correlations | Existing pairwise daily study plus multi-measurement hourly study, overlap thresholds and hourly observation counts |
| Spatial correlations | Coordinate-stability audit, deterministic bounded stable-sensor sample, haversine proximity and exact-time overlap gates |
| Lags | Existing previous 1/2 observations plus 6/12/24 observations, differences and guarded percent changes |
| Rolling features | Prior elapsed 7/30-day statistics plus range and current position relative to prior range |
| Interactions | Existing occupancy ratio, net revenue and particulate ratio plus explicitly named algebraic products for traffic/weather/energy |
| Trends | Existing aggregate OLS/recent slopes and adjacent-week changes plus per-sensor slope, span, count and R² |
| Handoff | Connected pipeline, unchanged original fields, availability report, persisted Parquet checks, lineage and completion checklist |

## Choices that protect interpretation

- Continue reading a completed, hashed Day 2 snapshot. No silent raw-data fallback, database access or overwrite of historical runs.
- The source file's centered pattern windows and forward changepoint windows include future observations. The revised review flags use prior history only. Centered decomposition is exported separately and never added to Day 4 feature tables.
- Decomposition is a transparent centered-seven-day trend plus zero-centered weekday effects and residuals. It is descriptive, not evidence of an annual cycle or a calibrated seasonal forecast. Gapped daily series are not filled to force a result.
- The default pattern rule is absolute deviation greater than three prior standard deviations. Insufficient history or zero variance yields an unassessed flag, not a false declaration of normality. It does not replace Day 4 alert models.
- Hourly means are sample-weighted observations, not matched-location data. Require 48 shared hours across 14 dates; do not use coefficients as causal evidence, significance tests or independent-sample estimates.
- Fixed-location spatial analysis requires one coordinate pair per sensor. Audit changing coordinates rather than collecting every location and treating each as a separate fixed sensor. Sample at most 50 stable IDs deterministically; report nearby pairs even when time overlap is insufficient. No imputation or nearest-time alignment is used.
- Lags are observations, not hours. Rolling features exclude the current timestamp and use elapsed days. Current differences, ratios, products and range positions must not predict the same current reading. Undefined denominators remain null; position can legitimately fall outside 0–1.
- Avoid the scaffold's uncalibrated heat-index, combined-pollution and efficiency labels. Algebraic products retain source-unit meaning without implying validated physical indices. Do not mix currencies, infer city profit or assume power units.
- Per-sensor slopes are descriptive OLS summaries with coverage, not significance claims. Existing adjacent-week differences are change indicators, not validated changepoints. No arbitrary epsilon converts missing history into apparent evidence.
- New columns are additive. Existing model inputs and original observations remain available; Day 4's chronological split and training-only preprocessing must remain in force.

## Outputs and reading order

1. `dashboard.html`: coverage, original charts, decomposition, pattern counts, spatial audit, hourly associations and expandable monthly/weekend tables.
2. `correlation_findings.md`, `trend_report.md`: original descriptive summaries.
3. `instructor_extensions/`: numerical evidence for added analyses, per-sensor trend Parquet and explicit unsupported spatial/decomposition statuses.
4. `feature_availability.csv`: missing-history rates for every engineered feature. Longer lags may be mostly or entirely unavailable.
5. `completion_checklist.json`, `manifest.json`: execution checks and exact upstream lineage. A completed spatial assessment is not a claim that spatial correlations were estimable.

Rerun Day 4 separately when ready to adopt the new Day 3 snapshot. Existing Day 4 and convention outputs remain historical artifacts and are not overwritten.
