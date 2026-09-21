"""Day 5 snapshot contracts and PostgreSQL publication. No automatic connections."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd
from psycopg.types.json import Jsonb

SCHEMA = "sparkcity_analytics_hakeem"
METRICS = {
    "traffic": ["vehicle_count", "avg_speed"],
    "air_quality": ["pm25", "pm10", "no2", "co"],
    "weather": ["temperature", "humidity", "wind_speed", "precipitation"],
    "energy": ["power_consumption", "voltage", "current", "power_factor"],
    "occupancy": ["available_rooms", "occupied_rooms", "guests"],
    "fiscal": ["revenue", "expense", "net_per_observation"],
}
KEYS = {k: "sensor_id" for k in METRICS} | {"weather": "station_id", "energy": "meter_id"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def dataset_hash(path):
    """Match the Day 4 snapshot hash, including relative filenames."""
    result = hashlib.sha256()
    for item in sorted(Path(path).rglob("*")):
        if item.is_file():
            result.update(str(item.relative_to(path)).encode())
            with item.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    result.update(block)
    return result.hexdigest()


def select_sources(root, day4_run=None):
    base = Path(root) / "data/processed/day4"
    if day4_run is not None and Path(day4_run).name != day4_run:
        raise ValueError("Use a run directory name, not a path")
    complete = sorted(p.parent for p in base.glob("*/manifest.json")
                      if json.loads(p.read_text()).get("status") == "complete")
    day4 = base / day4_run if day4_run else (complete[-1] if complete else None)
    if day4 is None:
        raise ValueError("Complete Day 4 first")
    manifest = json.loads((day4 / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("outlier_policy") != "flag":
        raise ValueError("Day 4 must be complete and use flag-only inputs")
    for key in ("day1_run", "day2_run", "day3_run"):
        if not manifest.get(key) or Path(manifest[key]).name != manifest[key]:
            raise ValueError("Missing or invalid source lineage")
    day3 = Path(root) / "data/processed/day3" / manifest["day3_run"]
    raw = (day3 / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["day3_manifest_sha256"]:
        raise ValueError("Day 3 manifest changed since Day 4")
    previous = json.loads(raw)
    if previous.get("status") != "complete" or any(
        previous.get(k) != manifest[k] for k in ("day1_run", "day2_run")
    ):
        raise ValueError("Inconsistent source lineage")
    if set(manifest["input_sha256"]) != set(METRICS):
        raise ValueError("All six temporal datasets are required")
    for kind, expected in manifest["input_sha256"].items():
        path = day3 / "features" / kind
        if not path.is_dir() or dataset_hash(path) != expected:
            raise ValueError(f"Changed or missing Day 3 input: {kind}")
    return day4, day3, manifest, previous


def aggregate_daily(spark, day3, previous):
    """Spark aggregates all dates; only compact daily results reach the driver."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import NumericType, StringType
    from sparkcityx.data_quality import get_validation_config, validate_dataframe

    counts = {r["dataset"]: r["rows"] for r in previous["features"]}
    output, audits = [], []
    for kind, measurements in METRICS.items():
        frame = spark.read.parquet(str(day3 / "features" / kind)).select(
            *get_validation_config(kind)["required_columns"]).cache()
        cached = frame
        try:
            report = validate_dataframe(frame, kind)
            if not report["valid"] or report["record_count"] != counts[kind]:
                raise ValueError(f"Input contract failed: {kind}")
            # Local publication guard; the shared validator is deliberately unchanged.
            tests = []
            for field in frame.schema.fields:
                value = F.col(field.name)
                if isinstance(field.dataType, NumericType):
                    tests.append(F.sum(F.when(F.isnan(value) | (F.abs(value) == float("inf")), 1)
                                       .otherwise(0)).alias(field.name))
                elif isinstance(field.dataType, StringType):
                    tests.append(F.sum(F.when(F.length(F.trim(value)) == 0, 1)
                                       .otherwise(0)).alias(field.name))
            if any(frame.agg(*tests).first()):
                raise ValueError(f"Blank or nonfinite required values: {kind}")
            if kind == "fiscal":
                frame = frame.withColumn("net_per_observation", F.col("revenue") - F.col("expense"))
            for metric in measurements:
                if not isinstance(frame.schema[metric].dataType, NumericType):
                    raise ValueError(f"Nonnumeric metric: {kind}/{metric}")
            expressions = [F.count("*").alias("observations"),
                           F.countDistinct(KEYS[kind]).alias("sensors")]
            for metric in measurements:
                expressions += [F.avg(metric).alias(metric + "__mean"),
                                F.min(metric).alias(metric + "__minimum"),
                                F.max(metric).alias(metric + "__maximum")]
            daily = frame.groupBy(F.to_date("timestamp").alias("day")).agg(*expressions).orderBy("day").collect()
            for row in daily:
                for metric in measurements:
                    output.append({"dataset": kind, "metric": metric, "day": str(row.day),
                                   "observations": row.observations, "sensors": row.sensors,
                                   **{name: float(row[metric + "__" + name])
                                      for name in ("mean", "minimum", "maximum")}})
            audits.append({"dataset": kind, "rows": report["record_count"], "days": len(daily)})
            print(f"{kind}: {report['record_count']:,} rows -> {len(daily)} daily groups", flush=True)
        finally:
            # Unpersist the original cached logical plan even after adding fiscal columns.
            cached.unpersist()
    return output, audits


def read_alerts(day4, manifest):
    alerts = []
    for audit in manifest["anomalies"]:
        kind = audit["dataset"]
        frame = pd.read_parquet(day4 / "alerts" / kind)
        if len(frame) != audit["alert_rows"] or not frame["is_alert"].all():
            raise ValueError(f"Alert count/flag mismatch: {kind}")
        if not frame["_day3_run_id"].eq(manifest["day3_run"]).all():
            raise ValueError("Alert lineage mismatch")
        for r in frame.to_dict("records"):
            alerts.append({"alert_id": r["alert_id"], "dataset": kind,
                           "sensor_id": r[KEYS[kind]], "observed_at": r["timestamp"].isoformat(),
                           "reasons": r["alert_reasons"], "model_id": r["model_id"],
                           "severity": r["severity"]})
    return sorted(alerts, key=lambda r: (r["observed_at"], r["alert_id"]))


def validate_bundle(bundle):
    if bundle.get("status") != "complete" or not bundle.get("run_id"):
        raise ValueError("Only complete, identified snapshots can be published")
    if set(r["dataset"] for r in bundle["daily"]) != set(METRICS):
        raise ValueError("Six datasets required")
    keys = set()
    for r in bundle["daily"]:
        key = (r["dataset"], r["metric"], r["day"])
        if key in keys or r["metric"] not in METRICS[r["dataset"]]:
            raise ValueError("Duplicate or unsupported daily key")
        keys.add(key)
        date.fromisoformat(r["day"])
        if not all(math.isfinite(r[c]) for c in ("mean", "minimum", "maximum")):
            raise ValueError("Nonfinite aggregate")
        if not r["minimum"] <= r["mean"] <= r["maximum"]:
            raise ValueError("Inconsistent aggregate bounds")
        if any(type(r[c]) is not int for c in ("sensors", "observations")) or not 0 < r["sensors"] <= r["observations"]:
            raise ValueError("Invalid aggregate counts")
    if {(r["dataset"], r["metric"]) for r in bundle["daily"]} != {
        (k, m) for k, metrics in METRICS.items() for m in metrics
    }:
        raise ValueError("Missing dashboard metrics")
    ids = set()
    for r in bundle["alerts"]:
        validate_alert(r)
        if r["alert_id"] in ids:
            raise ValueError("Duplicate alert")
        ids.add(r["alert_id"])
    digest(bundle)  # Reject non-JSON / NaN provenance too.


def validate_alert(row):
    if row["dataset"] not in METRICS or row["severity"] != "review":
        raise ValueError("Invalid alert dataset/severity")
    for key in ("alert_id", "sensor_id", "model_id", "reasons", "observed_at"):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError("Missing alert field: " + key)
    if pd.isna(pd.Timestamp(row["observed_at"])):
        raise ValueError("Invalid alert timestamp")


def setup_schema(connection, root):
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute((Path(root) / "sql/002_day5_analytics.sql").read_text())


def publish_bundle(connection, bundle):
    """Atomic immutable snapshot publication, safe identical retries, no raw writes."""
    validate_bundle(bundle)
    sha = digest(bundle)
    run_id = bundle["run_id"]
    with connection.transaction(), connection.cursor() as c:
        c.execute("SET LOCAL lock_timeout = '10s'")
        c.execute("SET LOCAL statement_timeout = '120s'")
        # Fixed advisory lock serializes this application's publications/retention.
        c.execute("SELECT pg_advisory_xact_lock(515005)")
        c.execute(f"SELECT payload_sha256 FROM {SCHEMA}.pipeline_run WHERE run_id=%s", (run_id,))
        existing = c.fetchone()
        if existing:
            if existing[0] != sha:
                raise ValueError("Run ID already exists with different content; use a new version")
            return {"status": "unchanged", "run_id": run_id}
        c.execute(f"INSERT INTO {SCHEMA}.pipeline_run(run_id,payload_sha256,provenance) VALUES (%s,%s,%s)",
                  (run_id, sha, Jsonb(bundle["provenance"])))
        dates = sorted({r["day"] for r in bundle["daily"]})
        c.executemany(f"INSERT INTO {SCHEMA}.dim_date VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                      [(d, date.fromisoformat(d).year, date.fromisoformat(d).month,
                        date.fromisoformat(d).weekday()) for d in dates])
        c.executemany(f"INSERT INTO {SCHEMA}.dim_metric VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                      [(k, m, "Observation mean; units unconfirmed; not a city total")
                       for k, metrics in METRICS.items() for m in metrics])
        c.executemany(f"INSERT INTO {SCHEMA}.fact_daily VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      [(run_id, r["dataset"], r["metric"], r["day"], r["observations"], r["sensors"],
                        r["mean"], r["minimum"], r["maximum"]) for r in bundle["daily"]])
        if bundle["alerts"]:
            c.executemany(f"INSERT INTO {SCHEMA}.fact_alert VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                          [(run_id, *(r[k] for k in ("alert_id", "dataset", "sensor_id", "observed_at",
                                                     "reasons", "model_id", "severity"))) for r in bundle["alerts"]])
        c.execute(f"INSERT INTO {SCHEMA}.publication(name,run_id) VALUES ('city_operations',%s) "
                  "ON CONFLICT(name) DO UPDATE SET run_id=EXCLUDED.run_id,published_at=CURRENT_TIMESTAMP", (run_id,))
        return {"status": "published", "run_id": run_id, "daily_rows": len(bundle["daily"])}


def write_stream_batch(connection, rows, stream_id, batch_id):
    """Idempotent historical alert replay + durable outbox in one transaction."""
    rows = sorted(rows, key=lambda r: r["alert_id"])
    for r in rows:
        validate_alert(r)
    if len({r["alert_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate alert IDs within batch")
    sha = digest(rows)
    with connection.transaction(), connection.cursor() as c:
        c.execute("SET LOCAL lock_timeout = '10s'")
        c.execute("SET LOCAL statement_timeout = '120s'")
        c.execute("SELECT pg_advisory_xact_lock(515006)")
        c.execute(f"SELECT content_sha256 FROM {SCHEMA}.stream_batch WHERE stream_id=%s AND batch_id=%s",
                  (stream_id, int(batch_id)))
        existing = c.fetchone()
        if existing:
            if existing[0] != sha:
                raise ValueError("Stream batch was replayed with changed content")
            return "unchanged"
        for r in rows:
            content_hash = digest(r)
            c.execute(f"SELECT content_sha256 FROM {SCHEMA}.stream_alert WHERE alert_id=%s", (r["alert_id"],))
            prior = c.fetchone()
            if prior and prior[0] != content_hash:
                raise ValueError("Alert ID already exists with changed content")
            c.execute(f"INSERT INTO {SCHEMA}.stream_alert "
                      "(alert_id,content_sha256,dataset,sensor_id,observed_at,reasons,model_id) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(alert_id) DO NOTHING",
                      (r["alert_id"], content_hash, r["dataset"], r["sensor_id"], r["observed_at"], r["reasons"], r["model_id"]))
            c.execute(f"INSERT INTO {SCHEMA}.notification_outbox(event_id,payload) VALUES (%s,%s) "
                      "ON CONFLICT(event_id) DO NOTHING", (r["alert_id"], Jsonb(r | {"replay": True})))
        c.execute(f"INSERT INTO {SCHEMA}.stream_batch(stream_id,batch_id,content_sha256,rows_seen) VALUES (%s,%s,%s,%s)",
                  (stream_id, int(batch_id), sha, len(rows)))
    return "committed"


def retention_candidates(connection, keep_days=90, apply=False):
    """Opt-in analytics snapshot retention; always preserves the published run."""
    if type(keep_days) is not int or keep_days < 1:
        raise ValueError("keep_days must be a positive integer")
    with connection.transaction(), connection.cursor() as c:
        c.execute("SET LOCAL lock_timeout = '10s'")
        c.execute("SELECT pg_advisory_xact_lock(515005)")
        c.execute(f"SELECT run_id FROM {SCHEMA}.pipeline_run WHERE created_at < "
                  "CURRENT_TIMESTAMP - (%s * INTERVAL '1 day') "
                  f"AND run_id NOT IN (SELECT run_id FROM {SCHEMA}.publication) ORDER BY run_id", (keep_days,))
        candidates = [r[0] for r in c.fetchall()]
        if apply and candidates:
            c.execute(f"DELETE FROM {SCHEMA}.pipeline_run WHERE run_id = ANY(%s)", (candidates,))
    return candidates


def read_publication(connection):
    from psycopg.rows import dict_row
    with connection.transaction(), connection.cursor(row_factory=dict_row) as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        c.execute("SET LOCAL statement_timeout = '15s'")
        c.execute(f"SELECT p.run_id,p.published_at,r.provenance FROM {SCHEMA}.publication p "
                  f"JOIN {SCHEMA}.pipeline_run r USING(run_id) WHERE name='city_operations'")
        publication = c.fetchone()
        if not publication:
            raise ValueError("No published snapshot")
        c.execute(f"SELECT dataset,metric,day,observations,sensors,mean,minimum,maximum "
                  f"FROM {SCHEMA}.fact_daily WHERE run_id=%s ORDER BY dataset,metric,day", (publication["run_id"],))
        daily = [dict(r, day=str(r["day"])) for r in c.fetchall()]
        c.execute(f"SELECT alert_id,dataset,sensor_id,observed_at,reasons,model_id,severity "
                  f"FROM {SCHEMA}.fact_alert WHERE run_id=%s ORDER BY observed_at,alert_id", (publication["run_id"],))
        alerts = [dict(r, observed_at=r["observed_at"].isoformat()) for r in c.fetchall()]
        c.execute(f"SELECT count(*) AS total,max(received_at) AS last_received FROM {SCHEMA}.stream_alert")
        replay = c.fetchone()
        c.execute(f"SELECT count(*) AS pending FROM {SCHEMA}.notification_outbox WHERE delivery_status='pending'")
        pending = c.fetchone()["pending"]
    return {"status": "complete", "run_id": publication["run_id"], "daily": daily, "alerts": alerts,
            "provenance": publication["provenance"], "published_at": publication["published_at"].isoformat(),
            "replayed_alerts": replay["total"], "pending_notifications": pending}
