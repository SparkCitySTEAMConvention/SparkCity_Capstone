-- Dedicated namespace: never alters sparkcity raw/source tables.
CREATE SCHEMA IF NOT EXISTS sparkcity_analytics_hakeem;
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.dim_date (
    day DATE PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6)
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.dim_metric (
    dataset TEXT NOT NULL, metric TEXT NOT NULL, interpretation TEXT NOT NULL,
    PRIMARY KEY(dataset, metric)
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.pipeline_run (
    run_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provenance JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.fact_daily (
    run_id TEXT REFERENCES sparkcity_analytics_hakeem.pipeline_run ON DELETE CASCADE,
    dataset TEXT NOT NULL, metric TEXT NOT NULL,
    day DATE NOT NULL REFERENCES sparkcity_analytics_hakeem.dim_date,
    observations BIGINT NOT NULL CHECK(observations > 0),
    sensors BIGINT NOT NULL CHECK(sensors > 0 AND sensors <= observations),
    mean DOUBLE PRECISION NOT NULL CHECK(mean > '-Infinity'::float8 AND mean < 'Infinity'::float8),
    minimum DOUBLE PRECISION NOT NULL CHECK(minimum > '-Infinity'::float8 AND minimum < 'Infinity'::float8),
    maximum DOUBLE PRECISION NOT NULL CHECK(maximum > '-Infinity'::float8 AND maximum < 'Infinity'::float8),
    PRIMARY KEY(run_id, dataset, metric, day),
    FOREIGN KEY(dataset, metric) REFERENCES sparkcity_analytics_hakeem.dim_metric,
    CHECK(minimum <= mean AND mean <= maximum)
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.fact_alert (
    run_id TEXT REFERENCES sparkcity_analytics_hakeem.pipeline_run ON DELETE CASCADE,
    alert_id TEXT NOT NULL, dataset TEXT NOT NULL, sensor_id TEXT NOT NULL,
    observed_at TIMESTAMP NOT NULL, reasons TEXT NOT NULL, model_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity = 'review'),
    PRIMARY KEY(run_id, alert_id)
);
CREATE INDEX IF NOT EXISTS day5_alert_lookup ON sparkcity_analytics_hakeem.fact_alert(run_id, dataset, observed_at);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.publication (
    name TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES sparkcity_analytics_hakeem.pipeline_run,
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- An outbox is a notification queue, not evidence that a person was notified.
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.notification_outbox (
    event_id TEXT PRIMARY KEY, payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK(delivery_status IN ('pending','delivered'))
);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.stream_alert (
    alert_id TEXT PRIMARY KEY, content_sha256 TEXT NOT NULL,
    dataset TEXT NOT NULL, sensor_id TEXT NOT NULL, observed_at TIMESTAMP NOT NULL,
    reasons TEXT NOT NULL, model_id TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    replay BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS day5_stream_time ON sparkcity_analytics_hakeem.stream_alert(received_at);
CREATE TABLE IF NOT EXISTS sparkcity_analytics_hakeem.stream_batch (
    stream_id TEXT NOT NULL, batch_id BIGINT NOT NULL,
    content_sha256 TEXT NOT NULL, rows_seen BIGINT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(stream_id, batch_id)
);
