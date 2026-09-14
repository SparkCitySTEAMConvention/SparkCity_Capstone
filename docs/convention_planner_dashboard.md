# S.T.E.A.M. convention planner dashboard

Audience: city planners preparing a Science, Technology, Engineering, Arts and Mathematics convention for approximately 15,000 attendees. The dashboard is the final deliverable; the notebook is its reproducible calculation engine.

## Run and use

Run all cells in `notebooks/Hakeem_convention_scenarios.ipynb` with the project environment. It uses local NumPy/pandas calculations, not Spark or S2. Each successful run prints a new `data/processed/convention/<run>/dashboard.html` path. Open it in a browser.

1. Select an access archetype, weather condition and event duration. All 27 combinations are available. These are not named venues or calendar forecasts.
2. Read the added event demand, keeping daily/hourly requirements separate from event totals.
3. Enter known residual capacity after ordinary demand. Blank is unknown; zero is a real zero. The dashboard compares entries with modeled weather-stress targets, not with a certified safety standard.
4. Compare three one-at-a-time operational experiments. Assumed implementation targets are not measured effectiveness or costed recommendations.
5. Download the selected case and capacity entries for discussion. Entries are local to the page and reset on reload; the JSON download preserves them. The download is not an approval or validated city record.
6. Collect sourced candidate information with the venue evidence and S.T.E.A.M. program worksheets.

`decision_brief.html` gives five planning insights; `scenario_explorer.html` retains all detailed scenario charts/tables. Share the complete run directory to preserve linked worksheets and supporting pages. The main dashboard itself embeds the data needed for its controls and requires no network services.

## New analyses and their limits

- **Weather-stress capacity envelope:** for each access/duration combination, use each draw's maximum across the three weather conditions, separately for four resources. Targets are observed 97.5th percentiles rounded upward. The four marginal exceedance fractions sum to at most 10%; actual joint empirical coverage is verified to be at least 90%. This is conditional on the authored draws, not a population reliability guarantee. The envelope does not assess venue occupancy, egress, electricity peak load, route bottlenecks or accessible service.
- **Operational interventions:** arrival window ×1.5, people/car +0.5, venue electricity intensity ×0.8. Evaluate each against identical baseline draws for all 27 cases (81 comparisons). Costs, adoption, additional service operations and behavior feedback are not modeled. Baseline scenario counts and assumptions remain distinguishable from these experiments.
- **Access tradeoffs:** hold weather and duration fixed; compare reduced private-car activity, additional transit passengers and separate organizer expenses. No invented composite score or automatic winning venue.
- **One extra day:** paired changes in resource demand, potential visitor receipts and organizer costs for 2→3 and 3→4 days. Receipts earned by visitors' service providers cannot be netted against organizer costs to claim city profit.
- **Evidence boundary:** attach a completed Day 4 run only if it matches the selected Day 3 manifest. Forecast metrics are context, never calibrated convention effects. Sensor-location instability and weak forecast performance remain explicit.
- **S.T.E.A.M. requirements:** equipment, demonstrations, loading, arts programming, workshops, accessibility, internet and staffing are questions to investigate. None is asserted to be a confirmed activity or assigned an invented resource load.

## Evidence versus assumptions

Confirmed by the user: approximate attendance and event theme. Everything else numerical is illustrative unless subsequently supplied and sourced. Live capacity entries are user-entered and unverified. Hotel supply, real venue/date options, local prices, weather probabilities, fleet emissions and program demands remain unknown. Air-quality concentration and convention-induced weather changes are not estimated.

Planning scope is informed by [FHWA event operations planning](https://ops.fhwa.dot.gov/publications/fhwaop04010/chapter3_05.htm) and [EPA green meetings](https://www.epa.gov/p2/green-meetings). Neither source validates the numerical assumptions or intervention sizes.

## Verification

The notebook checks all 27 baseline cases, paired-draw conservation, persisted sample counts, nine resource envelopes, 81 intervention comparisons and 18 duration increments. Intervention tests verify peak-versus-total distinctions and unchanged visitor/lodging demand. Dashboard controls should also be tested across all 27 selections with unknown, zero, below-target and at-target capacity entries. Model completion does not certify an event plan.
