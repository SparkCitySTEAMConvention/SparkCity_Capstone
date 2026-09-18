"""Repeatable local Day 5 build; publication and replay require explicit callers."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sparkcityx.day5 import (
    aggregate_daily, dataset_hash, digest, read_alerts, select_sources, validate_bundle,
)


def start_spark():
    from pyspark.sql import SparkSession
    java_home = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
    if not os.getenv("JAVA_HOME") and java_home.exists():
        os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    spark = (SparkSession.builder.master("local[2]").appName("Hakeem-Day5")
             .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "4")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def build_snapshot(root, spark, day4_run=None):
    root = Path(root)
    day4, day3, source, previous = select_sources(root, day4_run)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "data/processed/day5" / run_id
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps({"status": "running", "run_id": run_id}))
    inputs_before = {"day4_manifest": hashlib.sha256((day4 / "manifest.json").read_bytes()).hexdigest(),
                     "alerts": dataset_hash(day4 / "alerts")}
    try:
        print("Day 4 source:", day4.name, flush=True)
        daily, audit = aggregate_daily(spark, day3, previous)
        alerts = read_alerts(day4, source)
        provenance = {"day4_run": day4.name, "day3_run": day3.name,
                      "day2_run": source["day2_run"], "day1_run": source["day1_run"],
                      "source_units": source.get("source_units"),
                      "timestamp_semantics": source.get("timestamp_semantics"),
                      "processing_timezone": "UTC", "input_hashes": inputs_before,
                      "day3_input_hashes": source["input_sha256"], "spark": spark.version,
                      "audit": audit, "anomalies": source["anomalies"],
                      "created_at": datetime.now(timezone.utc).isoformat(),
                      "scope": "Synthetic observation means; not city totals or causal event effects"}
        bundle = {"status": "complete", "run_id": run_id, "daily": daily,
                  "alerts": alerts, "provenance": provenance}
        validate_bundle(bundle)
        fiscal = pd.DataFrame(daily).query("dataset == 'fiscal'")
        fiscal.to_csv(output / "fiscal_daily.csv", index=False)
        # Preserve the compact aggregate table and a complete alert-review export.
        pd.DataFrame(daily).to_parquet(output / "daily.parquet", index=False)
        pd.DataFrame(alerts).to_json(output / "alerts.json", orient="records", indent=2)
        from sparkcityx.day5_dashboard import render_dashboard
        (output / "dashboard.html").write_text(render_dashboard(bundle))
        # Streaming input files are bounded historical microbatches, not new readings.
        replay = output / "replay_input"
        replay.mkdir()
        for offset in range(0, len(alerts), 100):
            (replay / f"batch_{offset // 100:04d}.json").write_text(
                "".join(json.dumps(r) + "\n" for r in alerts[offset:offset + 100]))
        select_sources(root, day4.name)  # Recheck input hashes after aggregation.
        inputs_after = {"day4_manifest": hashlib.sha256((day4 / "manifest.json").read_bytes()).hexdigest(),
                        "alerts": dataset_hash(day4 / "alerts")}
        if inputs_before != inputs_after:
            raise ValueError("Inputs changed during the build")
        (output / "bundle.json").write_text(json.dumps(bundle, indent=2, allow_nan=False))
        manifest = {"status": "complete", "run_id": run_id, "day4_run": day4.name,
                    "bundle_sha256": digest(bundle), "daily_rows": len(daily), "alert_rows": len(alerts),
                    "database_publication": "not_attempted", "notification_delivery": "not_attempted"}
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("Completed local snapshot:", output, flush=True)
        return output, bundle
    except Exception as exc:
        # Do not persist arbitrary exception messages: connection errors may expose credentials.
        manifest_path.write_text(json.dumps({"status": "failed", "run_id": run_id,
                                              "error_type": type(exc).__name__}))
        raise


def load_snapshot(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    bundle = json.loads((path / "bundle.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("bundle_sha256") != digest(bundle):
        raise ValueError("Incomplete or modified Day 5 snapshot")
    validate_bundle(bundle)
    return bundle


def replay_alert_stream(spark, output, connect):
    """Bounded Structured Streaming replay, persistent checkpoint, driver-side sink."""
    from sparkcityx.day5 import write_stream_batch
    from pyspark.sql.types import StructType, StructField, StringType
    output = Path(output)
    bundle = load_snapshot(output)
    schema = StructType([StructField(k, StringType(), False) for k in
                         ("alert_id", "dataset", "sensor_id", "observed_at", "reasons", "model_id", "severity")])
    # Verify replay input matches the validated snapshot before allowing database writes.
    rows = [json.loads(line) for p in sorted((output / "replay_input").glob("*.json"))
            for line in p.read_text().splitlines() if line.strip()]
    if sorted(rows, key=lambda r: r["alert_id"]) != sorted(bundle["alerts"], key=lambda r: r["alert_id"]):
        raise ValueError("Replay files differ from the completed snapshot")
    stream = spark.readStream.schema(schema).option("maxFilesPerTrigger", 1).json(str(output / "replay_input"))

    def sink(frame, batch_id):
        rows = [r.asDict() for r in frame.collect()]  # Bounded, 100 alerts per prepared file.
        with connect() as connection:
            write_stream_batch(connection, rows, bundle["run_id"], batch_id)

    query = (stream.writeStream.foreachBatch(sink)
             .option("checkpointLocation", str(output / "stream_checkpoint"))
             .trigger(availableNow=True).start())
    query.awaitTermination()
    return query.recentProgress
