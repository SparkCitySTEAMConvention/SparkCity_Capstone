# Convention model: decisions and evidence

## Objective and established fact

**Current planning update:** the proposed event is April 7–9, 2027 (Wednesday–Friday),
with approximately 15,000 attendees. These dates are inputs to the fiscal assessment,
not dates inferred by the historical simulation. See `docs/fiscal_analysis.md`.
The original assumptions and historical 27-scenario outputs below are retained unchanged;
their duration comparisons are not calendar forecasts.

Original simulation scope: explore the conditions under which Spark City could host approximately 15,000 attendees. At that stage, attendance was the only user-established event input. No venue, date, duration, visitor share, market price or capacity had been confirmed.

Update: the user also confirmed the S.T.E.A.M. theme: Science, Technology, Engineering, Arts and Mathematics. Attendance remains the only established numerical event input. The final deliverable is now an interactive city-planner dashboard, with the notebook as its calculation engine. See `docs/convention_planner_dashboard.md` for the added capacity envelopes, operational experiments, program requirements and evidence boundaries. No program-specific resource loads have been invented.

This document records the modeling rationale, assumptions and validation approach. The executable source is `notebooks/Hakeem_convention_scenarios.ipynb`; each run exports its assumptions and results.

## Modeling decisions

1. **Scenario accounting rather than causal prediction.** Existing synthetic data contain no labeled convention intervention or control group. Previously trained forecasting models cannot identify the convention's causal effects. The event model therefore calculates additional demand from explicit assumptions; synthetic daily profiles are context only.
2. **Unique attendee interpretation.** Treat 15,000 as unique people attending every event day. Compare two-, three- and four-day durations. This must change if the user means 15,000 total admissions.
3. **Hypothetical sites and timing.** Compare transit-focused, mixed-access and car-oriented archetypes under comfortable/dry, hot/dry and wet conditions. These are not actual Spark City locations or calendar forecasts. A transit advantage is intentionally encoded by lower car share and distance; it is not a learned finding.
4. **Weather is external.** Cooling and mode-choice multipliers describe weather-conditioned demand. The model does not estimate a convention-caused change in city weather.
5. **Air quality scope.** Estimate attendee private-vehicle activity. Optional verified fleet factors can produce emissions mass. Ambient concentrations require additional dispersion, meteorology, fleet and background information. No numerical factors are invented by default.
6. **Financial boundaries.** Report potential visitor hotel/nonhotel receipts, retained gross spending and separate organizer costs. Do not subtract costs incurred by one stakeholder from receipts earned by another to claim city profit. Tax revenue, GDP, multipliers and displacement are not estimated.
7. **Uncertainty interpretation.** Independent triangular stress-test inputs and common random draws make comparisons auditable. They are authored distributions, not survey estimates. Simulation quantiles are not confidence intervals; simulated constraint exceedance is not a calibrated risk probability.
8. **Capacity checks are optional and explicit.** Unknown capacity means unassessed. Input residual hotel, road-arrival, transit-passenger and daily-energy headroom only after subtracting normal demand. All four are required for joint screening. Venue capacity, grid peak kW and traffic delay still require more detailed models.
9. **Reproducible outputs.** Each run has a unique directory, fixed random seed, exported assumptions, full draws, comparison tables, checksums and a success manifest. Neither S2 nor source datasets are changed.

## Methodological evidence

- [FHWA event travel planning](https://ops.fhwa.dot.gov/publications/fhwaop04010/chapter1.htm): event impacts depend on attendance, arrival/departure patterns, venue location and adjacent roadway capacity. This supports the model's travel-demand structure, not its numerical stress-test assumptions.
- [EPA emissions and dispersion modeling](https://www.epa.gov/moves/how-do-i-model-emissions-intersection): emissions and ambient concentration analyses involve additional fleet/project and dispersion modeling. This supports leaving concentrations unestimated.

No external source validates the notebook's spending, energy, mode-share, room-sharing or weather-response values. Replace them with local evidence before recommending an actual date or venue.

## Calculation and validation notes

Demand accounts for one local arrival/departure per attendee per event day. All visiting attendees require modeled overnight accommodation; nights equal duration. Room demand is rounded up. Private-car counts account for vehicle occupancy. Model limits exclude additional transit operations, aircraft, freight, workers, companions and congestion feedback.

Checks cover deterministic draws, mode-share conservation, person-days, room-nights, zero-attendance demand, positive denominators and duration/weather directional behavior. Verify persisted sample count and artifact metadata after execution. Keep required room demand distinct from rooms actually supplied; receipts are potential if all demand is served.

## Information needed for a real decision

### September 14 revision: complete and readable scenario coverage

The original simulation calculated 27 cases, but its dashboard chart and median table showed only nine three-day cases. The revised dashboard has separate expandable two-, three- and four-day sections, each containing nine cases. Stable S01–S27 identifiers are labels, not rankings. Every case is included in the readable comparison CSV, numerical quantiles and full simulation draws.

The default assumptions and original demand formulas remain unchanged. Corrected Day 3 data and its upstream lineage are recorded as descriptive context, not used to calibrate unobserved convention effects. Peak transit passenger demand is now explicit, preventing lower car demand from being mistaken for sufficient transit capacity.

Charts use readable units instead of scientific notation. The report includes a worked example, distinguishes daily demand from event totals, explains repeated lodging/spending results, and labels missing capacity as unassessed. Air-quality concentrations and an actual venue/date recommendation remain unsupported. The successful-run manifest is written only after persistence checks pass.

### Evidence still needed

- Confirm attendee/admission definition, duration, overnight share, arrival/departure patterns and travel survey.
- Obtain candidate venue capacity/accessibility, road headroom, transit service and hotel catchments.
- Obtain candidate dates, competing events, baseline hotel occupancy and observed weather/climate data.
- Verify source measurement units, electricity profiles/capacity, fleet emission factors and local prices.
- Obtain organizer budget and income quotes; agree on stakeholders and objective before defining net financial benefit.
- Agree on feasible resource limits and acceptable tradeoffs before ranking actual candidates.
