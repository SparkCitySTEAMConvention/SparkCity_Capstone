# Convention suitability exports for 2025

The planner reads monthly_scores_2025.csv, weekly_scores_2025.csv and daily_scores_2025.csv. These are user-provided PostgreSQL exports supplied September 18, 2026. The daily export comes from daily_scores_2025_clean.csv, not the doubled original export. The raw database was not revalidated as part of this integration.

Weights: Capacity 30%, Fiscal 30%, Air Quality 15%, Weather 15%, Energy 10%. Traffic and temperature are excluded. Category definitions follow section 3 of the supplied convention analysis, with the user-approved addition of inverse-normalized power consumption. Occupancy uses the mean of per-observation occupied / (available + occupied) rates. Other inputs are period observation averages. Capacity averages normalized available rooms and inverse-normalized occupancy; Fiscal averages normalized revenue and net profit; Air Quality averages inverse-normalized PM2.5 and NO2; Weather uses inverse-normalized precipitation.

Each export normalizes across its own periods. Weekly scores exclude the two partial year-boundary weeks before normalization. There are 12 months, 51 full weeks and 365 days. Scores across these time scales are not directly comparable. Coverage day/record counts do not establish complete sensor coverage.

Exported totals were calculated before rounding and are authoritative at baseline. Sensitivity scenarios use rounded exported category scores and are approximate. Zero adjustment preserves the exported total exactly. Missing values propagate; undefined normalization ranges are not replaced with zero.

The page uses these saved exports consistently instead of mixing live inputs and older hardcoded scores. Refresh by replacing the three CSV files with compatible exports and rerunning the checks. The older convention_monthly_inputs_2025.csv is retained for provenance but is no longer loaded by this page. Historical scores are not 2027 forecasts, and room observations cannot be summed to prove accommodation for 15,000 attendees.
