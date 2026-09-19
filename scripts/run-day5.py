"""Local build by default. Database writes require explicit flags."""
import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from sparkcityx.day5 import publish_bundle, setup_schema
from sparkcityx.day5_pipeline import build_snapshot, load_snapshot, replay_alert_stream, start_spark
from sparkcityx.database import connect_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day4-run")
    parser.add_argument("--snapshot", type=Path, help="Reuse a completed Day 5 snapshot for safe publication retries")
    parser.add_argument("--apply", action="store_true", help="Publish to the dedicated analytics schema")
    parser.add_argument("--initialize-schema", action="store_true", help="Create the analytics tables; requires --apply")
    parser.add_argument("--replay", action="store_true", help="Write bounded historical alert stream/outbox; requires --apply")
    args = parser.parse_args()
    if (args.initialize_schema or args.replay) and not args.apply:
        parser.error("Database setup/replay requires --apply")
    if args.snapshot and args.day4_run:
        parser.error("Choose --snapshot or --day4-run")
    root = Path(__file__).resolve().parents[1]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    spark = None
    try:
        if args.snapshot:
            output, bundle = args.snapshot.resolve(), load_snapshot(args.snapshot)
        else:
            spark = start_spark()
            output, bundle = build_snapshot(root, spark, args.day4_run)
        if args.apply:
            load_dotenv(root / "secrets/.env", override=False)
            with connect_database() as connection:
                if args.initialize_schema:
                    setup_schema(connection, root)
                receipt = publish_bundle(connection, bundle)
            (output / "publication_receipt.json").write_text(json.dumps(receipt, indent=2))
            if args.replay:
                spark = spark or start_spark()
                replay_alert_stream(spark, output, connect_database)
        logging.info("Day 5 complete: %s; database_apply=%s", output, args.apply)
    except Exception as exc:
        logging.error("Day 5 failed (%s). No success claimed; inspect local manifest and retry the same snapshot when appropriate.", type(exc).__name__)
        raise SystemExit(1) from None
    finally:
        if spark:
            spark.stop()


if __name__ == "__main__":
    main()
