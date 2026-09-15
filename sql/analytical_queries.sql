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
