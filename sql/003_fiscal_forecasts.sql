-- Optional persistence for the fiscal model; does not modify raw/source tables.
CREATE SCHEMA IF NOT EXISTS sparkcity_analytics_hakeem;
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.fiscal_forecast_run (
    run_id TEXT PRIMARY KEY,
    payload_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provenance JSONB NOT NULL,
    model_artifact JSONB NOT NULL,
    evaluation_metrics JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.fiscal_prediction (
    run_id TEXT REFERENCES sparkcity_analytics_hakeem.fiscal_forecast_run,
    target TEXT NOT NULL CHECK(target IN ('revenue','expense')),
    target_day DATE NOT NULL, origin_day DATE NOT NULL,
    prediction_kind TEXT NOT NULL CHECK(prediction_kind IN ('test','next_day')),
    actual DOUBLE PRECISION,
    prediction DOUBLE PRECISION NOT NULL CHECK(prediction >= 0 AND prediction < 'Infinity'::float8),
    lower_bound DOUBLE PRECISION NOT NULL CHECK(lower_bound >= 0 AND lower_bound < 'Infinity'::float8),
    upper_bound DOUBLE PRECISION NOT NULL CHECK(upper_bound >= 0 AND upper_bound < 'Infinity'::float8),
    PRIMARY KEY(run_id,target,target_day,prediction_kind),
    CHECK(target_day = origin_day + 1),
    CHECK(lower_bound <= prediction AND prediction <= upper_bound),
    CHECK((prediction_kind='test' AND actual IS NOT NULL AND actual >= 0 AND actual < 'Infinity'::float8)
       OR (prediction_kind='next_day' AND actual IS NULL))
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.fiscal_forecast_publication (
    name TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES sparkcity_analytics_hakeem.fiscal_forecast_run,
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
