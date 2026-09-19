-- Export convention suitability scores for one 2025 time grain.
-- Run with psql and set grain to month, week, or day, for example:
-- psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -v grain=month --csv --quiet \
--   -f sql/export_convention_scores_2025.sql

WITH settings AS (
    SELECT
        :'grain'::text AS grain,
        DATE '2025-01-01' AS year_start,
        DATE '2026-01-01' AS year_end,
        CASE :'grain'::text
            WHEN 'month' THEN INTERVAL '1 month'
            WHEN 'week' THEN INTERVAL '1 week'
            WHEN 'day' THEN INTERVAL '1 day'
        END AS step
),
periods AS (
    SELECT
        s.grain,
        d::date AS period_key,
        GREATEST(d::date, s.year_start) AS start_date,
        LEAST((d + s.step)::date, s.year_end) - 1 AS end_date
    FROM settings s
    CROSS JOIN LATERAL generate_series(
        date_trunc(s.grain, s.year_start::timestamp),
        s.year_end::timestamp - INTERVAL '1 day',
        s.step
    ) AS dates(d)
    WHERE s.grain IN ('month', 'week', 'day')
),
occupancy AS (
    SELECT
        date_trunc(s.grain, o.timestamp)::date AS period_key,
        AVG(o.available_rooms::numeric) AS available_rooms,
        AVG(
            100.0 * o.occupied_rooms::numeric
            / NULLIF(
                o.available_rooms::numeric + o.occupied_rooms::numeric,
                0
            )
        ) AS occupancy_rate,
        COUNT(DISTINCT o.timestamp::date) FILTER (
            WHERE o.available_rooms IS NOT NULL
              AND o.occupied_rooms IS NOT NULL
              AND o.available_rooms::numeric + o.occupied_rooms::numeric > 0
        ) AS occupancy_days
    FROM sparkcity.occupancy_data o
    CROSS JOIN settings s
    WHERE o.timestamp >= s.year_start
      AND o.timestamp < s.year_end
    GROUP BY 1
),
fiscal AS (
    SELECT
        date_trunc(s.grain, f.timestamp)::date AS period_key,
        AVG(f.revenue::numeric) AS revenue,
        AVG(f.revenue::numeric - f.expense::numeric) AS net_profit,
        COUNT(DISTINCT f.timestamp::date) FILTER (
            WHERE f.revenue IS NOT NULL
              AND f.expense IS NOT NULL
        ) AS fiscal_days
    FROM sparkcity.fiscal_data f
    CROSS JOIN settings s
    WHERE f.timestamp >= s.year_start
      AND f.timestamp < s.year_end
    GROUP BY 1
),
air AS (
    SELECT
        date_trunc(s.grain, a.timestamp)::date AS period_key,
        AVG(a.pm25::numeric) AS pm25,
        AVG(a.no2::numeric) AS no2,
        COUNT(DISTINCT a.timestamp::date) FILTER (
            WHERE a.pm25 IS NOT NULL
              AND a.no2 IS NOT NULL
        ) AS air_days
    FROM sparkcity.air_quality a
    CROSS JOIN settings s
    WHERE a.timestamp >= s.year_start
      AND a.timestamp < s.year_end
    GROUP BY 1
),
weather AS (
    SELECT
        date_trunc(s.grain, w.timestamp)::date AS period_key,
        AVG(w.precipitation::numeric) AS precipitation,
        COUNT(DISTINCT w.timestamp::date) FILTER (
            WHERE w.precipitation IS NOT NULL
        ) AS weather_days
    FROM sparkcity.weather_data w
    CROSS JOIN settings s
    WHERE w.timestamp >= s.year_start
      AND w.timestamp < s.year_end
    GROUP BY 1
),
energy AS (
    SELECT
        date_trunc(s.grain, e.timestamp)::date AS period_key,
        AVG(e.power_consumption::numeric) AS power,
        COUNT(DISTINCT e.timestamp::date) FILTER (
            WHERE e.power_consumption IS NOT NULL
        ) AS energy_days
    FROM sparkcity.energy_meters e
    CROSS JOIN settings s
    WHERE e.timestamp >= s.year_start
      AND e.timestamp < s.year_end
    GROUP BY 1
),
measurements AS (
    SELECT
        p.grain,
        p.start_date,
        p.end_date,
        o.available_rooms,
        o.occupancy_rate,
        f.revenue,
        f.net_profit,
        a.pm25,
        a.no2,
        w.precipitation,
        e.power,
        COALESCE(o.occupancy_days, 0) AS occupancy_days,
        COALESCE(f.fiscal_days, 0) AS fiscal_days,
        COALESCE(a.air_days, 0) AS air_days,
        COALESCE(w.weather_days, 0) AS weather_days,
        COALESCE(e.energy_days, 0) AS energy_days
    FROM periods p
    LEFT JOIN occupancy o USING (period_key)
    LEFT JOIN fiscal f USING (period_key)
    LEFT JOIN air a USING (period_key)
    LEFT JOIN weather w USING (period_key)
    LEFT JOIN energy e USING (period_key)
    WHERE p.grain <> 'week'
       OR p.end_date - p.start_date + 1 = 7
),
normalized AS (
    SELECT
        *,
        100.0 * (available_rooms - MIN(available_rooms) OVER ())
            / NULLIF(MAX(available_rooms) OVER () - MIN(available_rooms) OVER (), 0)
            AS room_score,
        100.0 * (MAX(occupancy_rate) OVER () - occupancy_rate)
            / NULLIF(MAX(occupancy_rate) OVER () - MIN(occupancy_rate) OVER (), 0)
            AS occupancy_score,
        100.0 * (revenue - MIN(revenue) OVER ())
            / NULLIF(MAX(revenue) OVER () - MIN(revenue) OVER (), 0)
            AS revenue_score,
        100.0 * (net_profit - MIN(net_profit) OVER ())
            / NULLIF(MAX(net_profit) OVER () - MIN(net_profit) OVER (), 0)
            AS profit_score,
        100.0 * (MAX(pm25) OVER () - pm25)
            / NULLIF(MAX(pm25) OVER () - MIN(pm25) OVER (), 0)
            AS pm25_score,
        100.0 * (MAX(no2) OVER () - no2)
            / NULLIF(MAX(no2) OVER () - MIN(no2) OVER (), 0)
            AS no2_score,
        100.0 * (MAX(precipitation) OVER () - precipitation)
            / NULLIF(MAX(precipitation) OVER () - MIN(precipitation) OVER (), 0)
            AS weather_score,
        100.0 * (MAX(power) OVER () - power)
            / NULLIF(MAX(power) OVER () - MIN(power) OVER (), 0)
            AS energy_score
    FROM measurements
),
categories AS (
    SELECT
        *,
        (room_score + occupancy_score) / 2.0 AS capacity_score,
        (profit_score + revenue_score) / 2.0 AS fiscal_score,
        (pm25_score + no2_score) / 2.0 AS air_quality_score
    FROM normalized
),
scored AS (
    SELECT
        *,
        capacity_score * 0.30
        + fiscal_score * 0.30
        + air_quality_score * 0.10
        + weather_score * 0.10
        + energy_score * 0.20 AS suitability_score
    FROM categories
)
SELECT
    grain AS period_type,
    start_date,
    end_date,
    CASE WHEN grain = 'day' THEN start_date END AS score_date,
    CASE WHEN grain = 'day' THEN to_char(start_date, 'FMDay') END AS weekday,
    CASE
        WHEN suitability_score IS NOT NULL THEN
            RANK() OVER (ORDER BY suitability_score DESC NULLS LAST)
    END AS suitability_rank,
    ROUND(capacity_score, 2) AS capacity,
    ROUND(fiscal_score, 2) AS fiscal,
    ROUND(air_quality_score, 2) AS air_quality,
    ROUND(weather_score, 2) AS weather,
    ROUND(energy_score, 2) AS energy,
    ROUND(suitability_score, 2) AS suitability,
    end_date - start_date + 1 AS expected_days,
    occupancy_days,
    fiscal_days,
    air_days,
    weather_days,
    energy_days,
    CASE
        WHEN suitability_score IS NULL THEN 'Unavailable'
        ELSE 'Calculated'
    END AS score_status
FROM scored
ORDER BY suitability_score DESC NULLS LAST, start_date;
