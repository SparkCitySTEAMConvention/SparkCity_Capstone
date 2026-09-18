-- Day 4 · Rotate SQL work across datasets (issue #42)
-- Sloane owns Occupancy; this query rotates onto Weather (owned by Leigh/Matt/Monah)
-- to answer a cross-dataset business question: does weather affect hotel occupancy?

-- Hourly occupancy rate, joined against hourly weather conditions.
WITH occupancy_hourly AS (
    SELECT
        date_trunc('hour', timestamp) AS hour_bucket,
        avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate,
        avg(guests) AS avg_guests,
        count(*) AS occupancy_readings
    FROM sparkcity.occupancy_data
    GROUP BY 1
),
weather_hourly AS (
    SELECT
        date_trunc('hour', timestamp) AS hour_bucket,
        avg(temperature) AS avg_temperature,
        avg(precipitation) AS avg_precipitation,
        avg(wind_speed) AS avg_wind_speed,
        count(*) AS weather_readings
    FROM sparkcity.weather_data
    GROUP BY 1
)
SELECT
    o.hour_bucket,
    round(o.avg_occupancy_rate::numeric, 4) AS avg_occupancy_rate,
    round(o.avg_guests::numeric, 2) AS avg_guests,
    round(w.avg_temperature::numeric, 2) AS avg_temperature,
    round(w.avg_precipitation::numeric, 3) AS avg_precipitation,
    round(w.avg_wind_speed::numeric, 2) AS avg_wind_speed
FROM occupancy_hourly o
JOIN weather_hourly w USING (hour_bucket)
ORDER BY o.hour_bucket;

-- Business question: is occupancy higher during rainy hours than dry hours?
WITH occupancy_hourly AS (
    SELECT
        date_trunc('hour', timestamp) AS hour_bucket,
        avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate
    FROM sparkcity.occupancy_data
    GROUP BY 1
),
weather_hourly AS (
    SELECT
        date_trunc('hour', timestamp) AS hour_bucket,
        avg(precipitation) AS avg_precipitation
    FROM sparkcity.weather_data
    GROUP BY 1
)
SELECT
    CASE WHEN w.avg_precipitation > 0 THEN 'rain' ELSE 'no_rain' END AS precip_bucket,
    round(avg(o.avg_occupancy_rate)::numeric, 4) AS avg_occupancy_rate,
    count(*) AS hour_count
FROM occupancy_hourly o
JOIN weather_hourly w USING (hour_bucket)
GROUP BY 1
ORDER BY 1;

-- Findings (run against shared sparkcity schema, 2026-09-15):
-- - 8,999 hourly buckets joined cleanly across occupancy_data and weather_data.
-- - avg_occupancy_rate is ~0.71 in both rain (7,998 hrs) and no_rain (1,001 hrs)
--   buckets -- no meaningful weather effect on occupancy in this dataset.
-- - Consistent with the Day 3 finding that the generated data is clean/random
--   by construction, so this is a real negative result, not a bug.

-- =============================================================================
-- Day 5 · Capacity & Infrastructure dashboard section (Sloane)
-- Business question: when does the city have spare capacity, and what date
-- does that recommend for the STEAM convention -- independent of the other
-- dashboard sections?
-- =============================================================================

-- Monthly room capacity: how full is the city, and how much headroom is left.
WITH occupancy_monthly AS (
    SELECT
        date_trunc('month', timestamp) AS month,
        count(*) AS readings,
        avg(available_rooms) AS avg_available_rooms,
        avg(occupied_rooms) AS avg_occupied_rooms,
        avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate
    FROM sparkcity.occupancy_data
    WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'  -- one full calendar year
    GROUP BY 1
)
SELECT
    to_char(month, 'Mon') AS month_name,
    readings,
    round(avg_available_rooms::numeric, 1) AS avg_available_rooms,
    round(avg_occupied_rooms::numeric, 1) AS avg_occupied_rooms,
    round(avg_occupancy_rate::numeric, 4) AS avg_occupancy_rate,
    round((100 * (1 - avg_occupancy_rate))::numeric, 1) AS headroom_pct,
    round((avg_available_rooms - avg_occupied_rooms)::numeric, 1) AS avg_available_capacity_rooms
FROM occupancy_monthly
ORDER BY month;

-- Monthly infrastructure load: does the power grid look stressed in any month.
SELECT
    to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
    count(*) AS readings,
    round(avg(power_consumption)::numeric, 2) AS avg_power_kw,
    round(stddev(power_consumption)::numeric, 2) AS std_power_kw,
    round(max(power_consumption)::numeric, 2) AS max_power_kw
FROM sparkcity.energy_meters
GROUP BY 1, date_trunc('month', timestamp)
ORDER BY date_trunc('month', timestamp);

-- Combined ranking: best-capacity months, restricted to months where BOTH
-- occupancy and energy data exist (energy_meters only covers Jan-Sep 2025 at
-- the time of this analysis), ordered by available headroom.
WITH occupancy_monthly AS (
    SELECT
        date_trunc('month', timestamp) AS month,
        avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate
    FROM sparkcity.occupancy_data
    WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
    GROUP BY 1
),
energy_monthly AS (
    SELECT
        date_trunc('month', timestamp) AS month,
        avg(power_consumption) AS avg_power_kw,
        max(power_consumption) AS max_power_kw
    FROM sparkcity.energy_meters
    GROUP BY 1
)
SELECT
    to_char(o.month, 'Mon') AS month_name,
    round((100 * (1 - o.avg_occupancy_rate))::numeric, 1) AS headroom_pct,
    round(e.avg_power_kw::numeric, 2) AS avg_power_kw,
    round(e.max_power_kw::numeric, 2) AS max_power_kw
FROM occupancy_monthly o
JOIN energy_monthly e USING (month)          -- inner join: only high-confidence months
ORDER BY headroom_pct DESC;

-- Findings (run against shared sparkcity schema, 2026-09-16):
-- - Occupancy has a real, strong seasonal shape (not the flat/random pattern
--   found in the Day 4 weather rotation): headroom ranges from ~42% in
--   December down to ~17% in June. Summer (May-Jul) is consistently the
--   tightest capacity window; winter (Nov-Jan) is consistently the loosest.
-- - energy_meters only has readings through 2025-09-07, so Oct/Nov/Dec have
--   NO infrastructure confirmation yet -- includes December, which has the
--   single best room-headroom number (42.3%). It cannot be recommended with
--   full confidence until infrastructure data catches up.
-- - Among months with BOTH occupancy and energy data, January has the best
--   headroom (40.2%) with unremarkable, typical energy load (44.07 kW avg,
--   141 kW max -- in line with every other measured month).
-- - Energy load itself is nearly flat across all measured months (43.4-44.7
--   kW avg, <3% spread) -- infrastructure load is not the binding constraint
--   here, room/venue occupancy is. The one exception is June's max_power_kw
--   of 154.86, the single highest instantaneous reading in the dataset --
--   consistent with June also being the worst month for room headroom.
-- - Recommendation from Capacity & Infrastructure data alone: January is the
--   best fully-confirmed month; December looks even better on raw room
--   capacity but needs infrastructure data collected before it can be
--   recommended. June/May/July are the months to avoid.

-- =============================================================================
-- Day 6 · Capacity & Infrastructure impact of the April 6-8, 2027 convention
-- date (Sloane). The multi-factor Convention Planner (weather, traffic, air
-- quality, fiscal) landed on April 6-8, 2027 -- a Tuesday-Thursday. This
-- section answers, from occupancy data alone: does the city have enough
-- spare room capacity to absorb ~15,000 extra attendees on those specific
-- dates, without inventing a per-person energy/traffic coefficient the team
-- agreed (Convention Impact and Dashboard Planning.md) not to fabricate.
-- =============================================================================

-- City-wide total room capacity for April: available_rooms is NOT constant
-- per sensor (it fluctuates like a live inventory feed), so "total capacity"
-- is the sum of each sensor's own April-average available_rooms across all
-- 1,200 sensors -- not a naive SUM(available_rooms) grouped by timestamp,
-- which would undercount because sensors report on a rotating ~12.5-day
-- cycle (only ~96 of 1,200 sensors report on any given day).
WITH per_sensor_april AS (
    SELECT
        sensor_id,
        avg(available_rooms) AS avg_capacity,
        avg(occupied_rooms) AS avg_occupied,
        avg(guests) AS avg_guests
    FROM sparkcity.occupancy_data
    WHERE timestamp >= '2025-04-01' AND timestamp < '2025-05-01'
    GROUP BY sensor_id
)
SELECT
    round(sum(avg_capacity)::numeric, 0) AS total_city_capacity_rooms,
    round(sum(avg_occupied)::numeric, 0) AS total_typical_occupied_rooms,
    round(sum(avg_guests)::numeric, 0) AS total_typical_guests,
    round((sum(avg_guests) / nullif(sum(avg_occupied), 0))::numeric, 3) AS guests_per_occupied_room
FROM per_sensor_april;

-- Tuesday-Thursday occupancy rate vs. every other day, April only. Occupancy
-- RATE (not raw counts) is used here because it is robust to the rotating
-- sensor sample -- unlike a raw room total, a ratio doesn't depend on which
-- subset of the 1,200 sensors happened to report that day.
SELECT
    CASE WHEN extract(dow FROM timestamp) IN (2, 3, 4) THEN 'Tue-Thu' ELSE 'Other' END AS day_group,
    round(avg(occupied_rooms::numeric / nullif(available_rooms, 0))::numeric, 4) AS avg_occupancy_rate,
    count(*) AS readings
FROM sparkcity.occupancy_data
WHERE timestamp >= '2025-04-01' AND timestamp < '2025-05-01'
GROUP BY 1;

-- Day-of-week occupancy rate across the full year, to confirm the Tue-Thu
-- dip is a stable weekly pattern rather than an April fluke.
SELECT
    to_char(timestamp, 'Dy') AS day_name,
    round(avg(occupied_rooms::numeric / nullif(available_rooms, 0))::numeric, 4) AS avg_occupancy_rate
FROM sparkcity.occupancy_data
WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
GROUP BY 1, extract(dow FROM timestamp)
ORDER BY extract(dow FROM timestamp);

-- Energy load, calendar 2025 (energy_meters now runs through Feb 2027; 2025
-- is used so every month lines up with the occupancy year), plus every
-- observed April for a cross-year check. Context only -- no capacity ceiling
-- exists in the energy or traffic data to compute headroom against.
SELECT
    to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
    round(avg(power_consumption)::numeric, 2) AS avg_power_kw,
    round(max(power_consumption)::numeric, 2) AS max_power_kw
FROM sparkcity.energy_meters
WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
GROUP BY date_trunc('month', timestamp)
ORDER BY date_trunc('month', timestamp);

SELECT
    extract(year FROM timestamp)::int AS year,
    round(avg(power_consumption)::numeric, 2) AS avg_power_kw,
    round(max(power_consumption)::numeric, 2) AS max_power_kw
FROM sparkcity.energy_meters
WHERE extract(month FROM timestamp) = 4
GROUP BY 1
ORDER BY 1;

-- Traffic congestion share by month, calendar 2025 (traffic_sensors now covers
-- all of 2025 plus a partial Jan 2026).
SELECT
    to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
    round(avg(vehicle_count)::numeric, 1) AS avg_vehicle_count,
    round(100.0 * sum(CASE WHEN congestion_level = 'high' THEN 1 ELSE 0 END) / count(*), 1) AS pct_high_congestion
FROM sparkcity.traffic_sensors
WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
GROUP BY date_trunc('month', timestamp)
ORDER BY date_trunc('month', timestamp);

-- Findings (run against shared sparkcity schema, 2026-09-18):
-- - Total city occupancy-sensor capacity in April 2025: ~425,626 rooms across
--   1,200 sensors, with ~333,176 typically occupied (78.3% occupancy,
--   ~92,450 rooms of headroom) and 2.477 guests per occupied room.
-- - Tue-Thu is measurably lighter than the rest of the week, in April AND
--   year-round: April Tue-Thu occupancy is 75.16% vs. 79.44% on other April
--   days; the full-year day-of-week breakdown shows the same Mon-Fri dip
--   (68-69%) against Sat/Sun peaks (~77%). A discrete Fourier transform of
--   the full-year daily occupancy-rate series (see day6 notebook) confirms
--   this: after the dominant 365-day seasonal component, the single
--   strongest periodic signal in the whole series is a ~7.02-day cycle
--   (rank #2 of 183 frequency bins) -- a stable, predictable weekly rhythm,
--   not daily noise. That's why the Tue-Thu-specific rate, not the
--   whole-April average, is the right baseline for an April 6-8 event.
-- - Applying the Tue-Thu rate (75.16%) to total capacity gives ~319,860
--   rooms typically occupied on an April Tuesday-Thursday, leaving ~105,766
--   rooms of headroom BEFORE the convention.
-- - 15,000 extra attendees, at the observed 2.477 guests/occupied-room
--   ratio, need ~6,057 additional rooms -- 5.7% of that Tue-Thu headroom.
--   Projected post-convention occupancy: ~76.6% (+1.4 points), still below
--   the ordinary April weekend baseline (79.4%) and well below the tightest
--   month of the year, June (82.6% avg occupancy, from the Day 5 analysis).
-- - Energy now covers all 12 months of 2025 (and beyond): monthly average
--   load is flat at 43.67-44.64 kW, and April 2025 (43.99 kW avg, 133.19 kW
--   max) sits below the year's highest peak (140.61 kW, January). A second
--   observed April agrees (April 2026: 43.80 kW avg, 128.35 kW max), so the
--   April baseline is repeatable, not a one-year fluke. This supersedes the
--   Day 5 caveat that Oct-Dec had no infrastructure data.
-- - Traffic: 35.0% of April 2025 readings are at "high" congestion vs.
--   34.3-36.1% across all 12 months of 2025 -- no April-specific anomaly.
--   The baseline share is real and non-trivial, but it's a standing city
--   condition for the Mobility & Traffic section to size mitigations
--   against, not a reason to avoid this date.
