# MCC Convention Planner demo snapshot

Source: user-supplied sparkcity_monthly_inputs_2025.csv on September 18, 2026, exported from the planner's SELECT-only monthly aggregation of sparkcity tables.

Contains full-precision monthly averages for January–December 2025. Used only when the monthly database load fails or returns no usable capacity values. The page labels this fallback as a saved snapshot. It is not 2027 observed data or a replacement for the team-reported scores. Environmental normalization remains unreconciled with the team model.

Occupancy rate follows the repository contract: the monthly average of
`100 * occupied_rooms / available_rooms`, with zero-capacity rows excluded.

Live monthly loads and snapshot fallbacks are cached for 15 minutes; the page's Refresh monthly data button retries immediately. No credentials are included in this snapshot.
