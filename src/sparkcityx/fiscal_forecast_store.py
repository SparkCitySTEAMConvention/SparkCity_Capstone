"""Explicit opt-in PostgreSQL publication for completed fiscal forecast artifacts."""
from datetime import date
import hashlib
import json
import math

from psycopg.types.json import Jsonb

SCHEMA = "sparkcity_analytics_hakeem"


def validate_publication(bundle):
    if bundle.get("status") != "complete" or not bundle.get("run_id"):
        raise ValueError("Only completed forecast runs may be published")
    if bundle["artifact"].get("horizon_days") != 1 or set(bundle["artifact"]["models"]) != {"revenue", "expense"}:
        raise ValueError("Expected revenue and expense one-day models")
    seen, rows = set(), []
    for kind, records in (("test", bundle["predictions"]), ("next_day", bundle["next_day"])):
        if not records or {r["target"] for r in records} != {"revenue", "expense"}:
            raise ValueError("Both targets required for each prediction kind")
        if kind == "next_day" and len(records) != 2:
            raise ValueError("Exactly one next-day forecast per target required")
        for r in records:
            target_day = r["day"] if kind == "test" else r["target_day"]
            if (date.fromisoformat(target_day) - date.fromisoformat(r["origin_day"])).days != 1:
                raise ValueError("Prediction horizon is not one day")
            key = (kind, r["target"], target_day)
            if key in seen:
                raise ValueError("Duplicate prediction key")
            seen.add(key)
            if not all(math.isfinite(r[k]) for k in ("prediction", "lower", "upper")):
                raise ValueError("Nonfinite prediction")
            if not 0 <= r["lower"] <= r["prediction"] <= r["upper"]:
                raise ValueError("Invalid prediction bounds")
            actual = r["actual"] if kind == "test" else None
            if kind == "test" and actual is None:
                raise ValueError("Test prediction requires an observed actual value")
            if actual is not None and (not math.isfinite(actual) or actual < 0):
                raise ValueError("Invalid actual value")
            rows.append((bundle["run_id"], r["target"], target_day, r["origin_day"], kind,
                         actual, r["prediction"], r["lower"], r["upper"]))
    payload = json.dumps(bundle, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest(), rows


def publish_forecast(connection, bundle):
    sha, rows = validate_publication(bundle)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout='10s'")
        cursor.execute("SET LOCAL statement_timeout='120s'")
        cursor.execute("SELECT pg_advisory_xact_lock(515007)")
        cursor.execute(f"SELECT payload_sha256 FROM {SCHEMA}.fiscal_forecast_run WHERE run_id=%s", (bundle["run_id"],))
        existing = cursor.fetchone()
        if existing:
            if existing[0] != sha:
                raise ValueError("Existing fiscal run has different content; use a new version")
            return {"status": "unchanged", "run_id": bundle["run_id"]}
        cursor.execute(f"INSERT INTO {SCHEMA}.fiscal_forecast_run "
                       "(run_id,payload_sha256,provenance,model_artifact,evaluation_metrics) VALUES (%s,%s,%s,%s,%s)",
                       (bundle["run_id"], sha, Jsonb(bundle["provenance"]), Jsonb(bundle["artifact"]), Jsonb(bundle["metrics"])))
        cursor.executemany(f"INSERT INTO {SCHEMA}.fiscal_prediction VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
        cursor.execute(f"INSERT INTO {SCHEMA}.fiscal_forecast_publication(name,run_id) VALUES ('fiscal',%s) "
                       "ON CONFLICT(name) DO UPDATE SET run_id=EXCLUDED.run_id,published_at=CURRENT_TIMESTAMP", (bundle["run_id"],))
    return {"status": "published", "run_id": bundle["run_id"], "prediction_rows": len(rows)}
