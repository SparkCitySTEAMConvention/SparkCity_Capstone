# Fiscal Impact: analysis before dashboard implementation

The companion `notebooks/Hakeem_fiscal_model.ipynb` adds a one-day predictive experiment.
See [Fiscal predictive model and grading evidence](fiscal_model.md) for the Spark pipeline,
chronological evaluation, saved inference, database handoff and rubric mapping.

Run `notebooks/Hakeem_fiscal_analysis.ipynb` with the project's `.venv` kernel.
No Spark startup, S2 connection, new package installation or shared-dashboard edits
are needed. Outputs go to a unique, Git-ignored `data/processed/fiscal_analysis/<run>`
directory. Keep the directory together: `report.html` references its eight PNG charts.

## Planning inputs and evidence boundaries

- Proposed event: April 6–8, 2027, Tuesday–Thursday; approximately 15,000 attendees.
  (Updated 2026-09-17 to match the team's agreed convention dates; previously pinned
  to April 7–9, 2027 during independent development of this notebook.)
- Dates are planning inputs, not an optimum discovered by this analysis.
- Historical fiscal source is the pinned Day 3 snapshot behind completed Day 4
  `20260914T205935811311Z`; its hashes and lineage are verified.
- Coverage: 36,000 observations, January 1, 2025–January 10, 2026. Only one complete
  April, no observed 2027, and no convention treatment/control label.
- Currency, accounting period and flow-versus-snapshot meaning remain unconfirmed.
  Use source units per observation, not city totals, profit, GDP or tax revenue.
- Sensor locations change; sensor IDs are not fixed businesses. The current generator's
  fiscal zone-sampling rule does not cover all six zone types at this dataset size.

## Methods

1. Required-field, finite-value, timestamp, key and coordinate checks; coverage audit.
2. Daily means/medians, negative-observation share and complete-calendar trailing means.
3. Distribution plots, descriptive slopes/R², weekday boxes and monthly means with partial-month labels.
4. Complete-week weekend-minus-weekday differences; descriptive Pearson/rank correlations.
5. Prior-only 28-day median/MAD review flags. Incomplete history and zero scale are
   unassessed. The threshold is exploratory; flagged days are not removed automatically.
6. All five three-day windows within April 6–12 use the same inclusion rules: complete
   matching-weekday sequences wholly inside April 2025. Four analogues per candidate.
   Within-window means are observation weighted; across-window means weight windows equally.
   Min–max bands are historical ranges, not intervals for future outcomes. Overlapping
   candidates are not independent experiments.
7. Separate saved three-day convention scenarios preserve authored assumptions and
   5,000 draws per case. Weather-duplicate fiscal values are checked and not pooled as
   independent evidence. No fiscal calibration or date-specific price/weather adjustment.

CSV outputs contain the chart tables. `findings.md` reports the comparison even if the
selected dates do not have the highest analogue revenue. `manifest.json` is complete
only after exports and final checks; incomplete runs must not feed the dashboard.
No p-values, causal financial effects, or claims of statistical optimality are reported.

## Generator interpretation

Revenue includes authored annual seasonality and a 15% weekend multiplier; expense does
not receive these multipliers. Recovering them is validation of synthetic behavior,
not independent evidence of local economics. Whole-year slopes are not seasonally
adjusted growth estimates. Pooled correlations may reflect shared zone-type scales.

## Future Fiscal Impact page

Use the team's existing shell. Suggested order: proposed dates and scope; historical
patterns and coverage; weekday-only trade-offs; separately labeled convention scenarios;
limitations and provenance. Do not label synthetic readings “live city revenue.”
No page implementation or database publication is performed in this analysis task.

Before stronger claims, obtain venue/hotel quotes, attendance/admission definition,
overnight share and lodging nights, displacement estimates, organizer income/budget,
accounting units, and representative historical/event/control observations.

## Verification — September 17, 2026

- All notebook code cells executed successfully against the pinned fiscal snapshot.
- Final output: `data/processed/fiscal_analysis/20260917T190054663146Z`.
- Eight charts and 21 exported-file hashes verified; candidate and convention-scenario
  charts visually inspected for labels and accounting/uncertainty distinctions.
- Full regression suite: **84 passed, 8 skipped**. The skipped tests require an
  explicitly configured isolated PostgreSQL database; no database was used this turn.
- Includes 22 fiscal tests covering invalid values, missing calendar days, weighted
  comparisons, candidate completeness, prior-only flag behavior, known trend slopes,
  scenario lineage and rejection of changed/missing scenario inputs.
- Shared dashboard, source datasets, shared validator and raw loader remain unchanged.

## Verification — September 18, 2026 (dates reconciled to team proposal)

- `EVENT_START`/`EVENT_END`/`CANDIDATE_START`/`CANDIDATE_END` in `fiscal_analysis.py`
  moved from April 7–9/7–13 to April 6–8/6–12, 2027 to match the team's agreed
  Tuesday–Thursday convention dates. All notebook markdown/text and the one
  weekday assertion (`Tuesday`/`Thursday`) were updated to match; `tests/test_fiscal_analysis.py`'s
  two date-coupled assertions were recomputed from the actual new output, not hand-derived.
- Notebook re-executed end-to-end (`jupyter nbconvert --execute`) against the same
  pinned Day 3 fiscal snapshot (`20260914T142210469836Z`) and convention run
  (`20260914T211931530828Z`) — no source data changed.
- Final output: `data/processed/fiscal_analysis/20260918T013504001732Z`. All 21
  exported-file hashes verified against its own manifest.
- New pinned window's historical net revenue/observation: 191.01 (min 177.66, max
  203.94, 4 analogue days), a ~0.9-unit shift from the previous April 7–9 pinning
  (191.89) — the two windows overlap on 2 of 3 days, so the conclusion is materially
  unchanged. Highest-revenue candidate among the five is still April 9–11, still not
  the pinned window.
- Fiscal test suite: **22 passed** (`tests/test_fiscal_analysis.py`).
- `docs/notebook_workflow.md`'s April 7–9 reference was corrected to April 6–8 for
  consistency. `docs/fiscal_model.md`'s one-day-horizon example (illustrating why
  the predictive model can't reach the event date) was intentionally left as-is —
  the predictive-model notebook and its next-day forecast task are unaffected by
  this change and were not re-run.
