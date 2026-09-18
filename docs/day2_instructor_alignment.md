# Day 2 instructor alignment

Compared `day2_stuff.txt` with `notebooks/Hakeem_day2.ipynb`. The text is a teaching scaffold with TODOs and example assumptions, not a completed executable pipeline.

| Instructor topic | Notebook implementation |
|---|---|
| Comprehensive profiling | Shared validation, nulls, non-finite values, duplicates, distributions, categorical cardinality and top values |
| Sensor health | Per-sensor reading counts, completeness percentages/scores, measurement variance, constant-reading flags, relative freshness and observed intervals |
| Missing-data patterns | Per-sensor percentages plus hour-of-day and weekday reports for selected measurements |
| Interpolation | Tested, bounded within-sensor linear interpolation; no extrapolation or cross-sensor filling |
| Statistical/domain outliers | IQR/Z-score flags plus the shared domain contract |
| Treatment strategies | Production flagging or approved IQR clipping; fixture-tested removal and median replacement alternatives |
| Standardization | Timestamp/category normalization and explicit unit conversion only when source units are confirmed |
| Lineage and handoff | Day 1 snapshot checksums, source/run metadata, preserved values/flags, quarantine reasons, row accounting and verified Parquet exports |
| Completion | Exported checklist distinguishes executed checks from unresolved unit/schedule evidence |

## Deliberate differences

- Load the verified Day 1 snapshot, not raw files a second time. Preserve downstream schemas and zone metadata.
- The scaffold's health score of 100 and quality score of 0.85 are placeholders. Report a calculated measurement-completeness score with an explicit interpretation instead. Diagnostic status is not a calibrated malfunction label.
- Only confirmed per-sensor schedules support long-interval flags. A generator's five-minute dataset increment is not each sensor's reporting interval. Historical freshness is measured against the dataset maximum, not today's date.
- Constant readings require at least three observed values; near-constant/noisy thresholds require measurement-specific evidence.
- The scaffold's forward fill does not enforce its `max_gap_hours` argument. The notebook retains bounded interpolation and demonstrates it on dirty fixtures; production does not silently fill missing values.
- Clipping uses IQR bounds, not the scaffold's 5th/95th percentiles. Z-scores use population rather than sample standard deviation. Production remains flag-only by default.
- Do not adopt example unit labels or upper limits as verified measurements. Unknown source units and schedules remain explicit in the checklist.
- The scaffold's standardization starts again from the original frames and its save command is commented out. The notebook retains its connected cleaning pipeline and actual persisted-output checks.

Diagnostics are exported beneath each Day 2 run's `diagnostics/<dataset>/` directory. Missingness percentages describe existing measurement cells; absent rows require a reporting contract to quantify. Fiscal and occupancy diagnostics characterize reporting series, not necessarily physical sensor health.

Re-run Day 3 and then Day 4 only when you want them to adopt the new Day 2 snapshot. Existing outputs remain historical runs, not automatically refreshed results.
