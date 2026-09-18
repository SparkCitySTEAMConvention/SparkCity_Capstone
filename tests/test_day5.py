import copy
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sparkcityx.day5 import (
    METRICS, SCHEMA, digest, publish_bundle, read_publication,
    retention_candidates, setup_schema, validate_bundle, write_stream_batch,
)
from sparkcityx.day5_dashboard import render_dashboard
from sparkcityx.day5_pipeline import load_snapshot


@pytest.fixture
def bundle():
    return {"status": "complete", "run_id": "fixture-run-1", "provenance": {
        "day4_run": "fixture", "created_at": "2026-09-17T00:00:00Z"},
        "daily": [{"dataset": k, "metric": m, "day": "2025-01-01",
                   "observations": 10, "sensors": 2, "mean": 5., "minimum": 1., "maximum": 10.}
                  for k, metrics in METRICS.items() for m in metrics],
        "alerts": [{"alert_id": "fixture-alert-1", "dataset": "fiscal", "sensor_id": "FIS-1",
                    "observed_at": "2025-01-01T00:00:00", "reasons": "cluster_distance",
                    "model_id": "fixture-model", "severity": "review"}]}


def test_valid_bundle_and_render(bundle):
    validate_bundle(bundle)
    assert digest(bundle) == digest(copy.deepcopy(bundle))
    bundle["provenance"]["note"] = "</script><script>alert(1)</script>"
    html = render_dashboard(bundle)
    assert "</script><script>alert" not in html
    assert "const LIVE=false" in html
    assert "__PAYLOAD__" not in html
    assert "const LIVE=true" in render_dashboard(bundle, live=True)


@pytest.mark.parametrize("case", ["nan", "infinity", "counts", "bounds", "duplicate", "missing", "missing_metric", "alert", "incomplete"])
def test_bad_bundle_rejected_before_database(bundle, case):
    if case == "nan": bundle["daily"][0]["mean"] = float("nan")
    if case == "infinity": bundle["daily"][0]["maximum"] = float("inf")
    if case == "counts": bundle["daily"][0]["sensors"] = 11
    if case == "bounds": bundle["daily"][0]["mean"] = -1
    if case == "duplicate": bundle["daily"].append(bundle["daily"][0])
    if case == "missing": bundle["daily"] = [r for r in bundle["daily"] if r["dataset"] != "fiscal"]
    if case == "missing_metric": bundle["daily"].pop()
    if case == "alert": bundle["alerts"][0]["sensor_id"] = " "
    if case == "incomplete": bundle["status"] = "running"
    connection = MagicMock()
    with pytest.raises(ValueError):
        publish_bundle(connection, bundle)
    connection.transaction.assert_not_called()


def test_snapshot_tamper_detection(tmp_path, bundle):
    (tmp_path / "bundle.json").write_text(json.dumps(bundle))
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "complete", "bundle_sha256": digest(bundle)}))
    assert load_snapshot(tmp_path) == bundle
    bundle["daily"][0]["mean"] = 6
    (tmp_path / "bundle.json").write_text(json.dumps(bundle))
    with pytest.raises(ValueError, match="modified"):
        load_snapshot(tmp_path)


@pytest.fixture
def database():
    """Only an explicitly supplied disposable local PostgreSQL test database."""
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    dsn = os.getenv("SPARKCITY_DAY5_TEST_DSN")
    if not dsn:
        pytest.skip("Set SPARKCITY_DAY5_TEST_DSN for isolated PostgreSQL integration tests")
    config = conninfo_to_dict(dsn)
    host = config.get("host", "")
    isolated_socket = host.startswith("/private/tmp/sparkcity-day5-pg.")
    isolated_docker = (host == "127.0.0.1" and config.get("port") == "55439"
                       and config.get("dbname") == "sparkcity_day5_test")
    if not (isolated_socket or isolated_docker):
        pytest.fail("Integration tests require the isolated Day 5 socket or Docker test database")
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace(%s)", (SCHEMA,))
            if cursor.fetchone()[0] is not None:
                pytest.fail("Test schema already exists; refusing to overwrite it")
        setup_schema(connection, Path(__file__).resolve().parents[1])
        try:
            yield connection
        finally:
            # This fixture created this exact schema in its explicitly isolated cluster.
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


def test_database_publish_retry_conflict_and_readback(database, bundle):
    assert publish_bundle(database, bundle)["status"] == "published"
    assert publish_bundle(database, bundle)["status"] == "unchanged"
    published = read_publication(database)
    assert published["daily"] == sorted(bundle["daily"], key=lambda r: (r["dataset"], r["metric"], r["day"]))
    assert published["alerts"] == bundle["alerts"]
    changed = copy.deepcopy(bundle)
    changed["daily"][0]["mean"] = 6.
    with pytest.raises(ValueError, match="different content"):
        publish_bundle(database, changed)
    assert read_publication(database)["run_id"] == bundle["run_id"]
    changed["run_id"] = "fixture-run-2"
    assert publish_bundle(database, changed)["status"] == "published"
    publish_bundle(database, bundle)  # Retry older version must not change pointer.
    assert read_publication(database)["run_id"] == changed["run_id"]


def test_database_rolls_back_partial_snapshot(database, bundle):
    import psycopg
    publish_bundle(database, bundle)
    changed = copy.deepcopy(bundle)
    changed["run_id"] = "will-rollback"
    changed["daily"][-1]["observations"] = 10**30  # BIGINT destination failure, after run insert.
    with pytest.raises(psycopg.Error):
        publish_bundle(database, changed)
    with database.cursor() as c:
        c.execute(f"SELECT count(*) FROM {SCHEMA}.pipeline_run WHERE run_id='will-rollback'")
        assert c.fetchone()[0] == 0
    assert read_publication(database)["run_id"] == bundle["run_id"]


def test_database_stream_retry_and_outbox_atomicity(database, bundle):
    alerts = bundle["alerts"]
    assert write_stream_batch(database, alerts, "stream", 0) == "committed"
    assert write_stream_batch(database, alerts, "stream", 0) == "unchanged"
    assert write_stream_batch(database, alerts, "other-checkpoint", 0) == "committed"
    changed = copy.deepcopy(alerts)
    changed[0]["reasons"] = "changed"
    with pytest.raises(ValueError, match="changed content"):
        write_stream_batch(database, changed, "stream", 0)
    # Insert a new ID first, then conflict: both new alert and outbox must roll back.
    mixed = [dict(alerts[0], alert_id="a-new-alert"), changed[0]]
    with pytest.raises(ValueError, match="changed content"):
        write_stream_batch(database, mixed, "stream", 1)
    with database.cursor() as c:
        for table in ("stream_alert", "notification_outbox"):
            c.execute(f"SELECT count(*) FROM {SCHEMA}.{table}")
            assert c.fetchone()[0] == 1
        c.execute(f"SELECT count(*) FROM {SCHEMA}.stream_batch")
        assert c.fetchone()[0] == 2


def test_database_retention_preserves_active(database, bundle):
    publish_bundle(database, bundle)
    newer = dict(bundle, run_id="newer")
    publish_bundle(database, newer)
    with database.cursor() as c:
        c.execute(f"UPDATE {SCHEMA}.pipeline_run SET created_at=CURRENT_TIMESTAMP-INTERVAL '100 days'")
    assert retention_candidates(database) == [bundle["run_id"]]
    assert retention_candidates(database, apply=True) == [bundle["run_id"]]
    assert read_publication(database)["run_id"] == "newer"


def test_database_concurrent_identical_publication(database, bundle):
    import psycopg
    from concurrent.futures import ThreadPoolExecutor

    def publish():
        with psycopg.connect(os.environ["SPARKCITY_DAY5_TEST_DSN"], autocommit=True) as connection:
            return publish_bundle(connection, bundle)["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert sorted(results) == ["published", "unchanged"]
    assert len(read_publication(database)["daily"]) == len(bundle["daily"])


def test_database_structured_stream_replay(database, bundle, tmp_path, spark):
    import psycopg
    from sparkcityx.day5_pipeline import replay_alert_stream
    (tmp_path / "bundle.json").write_text(json.dumps(bundle))
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "complete", "bundle_sha256": digest(bundle)}))
    inputs = tmp_path / "replay_input"
    inputs.mkdir()
    (inputs / "batch_0000.json").write_text(json.dumps(bundle["alerts"][0]) + "\n")

    def connect():
        return psycopg.connect(os.environ["SPARKCITY_DAY5_TEST_DSN"], autocommit=True)

    replay_alert_stream(spark, tmp_path, connect)
    replay_alert_stream(spark, tmp_path, connect)
    with database.cursor() as c:
        for table in ("stream_alert", "notification_outbox", "stream_batch"):
            c.execute(f"SELECT count(*) FROM {SCHEMA}.{table}")
            assert c.fetchone()[0] == 1
    (inputs / "batch_0000.json").write_text(json.dumps(dict(bundle["alerts"][0], reasons="changed")))
    with pytest.raises(ValueError, match="Replay files differ"):
        replay_alert_stream(spark, tmp_path, connect)


def test_database_dashboard_http(database, bundle):
    import psycopg
    import runpy
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen
    from urllib.error import HTTPError

    publish_bundle(database, bundle)
    root = Path(__file__).resolve().parents[1]
    make_handler = runpy.run_path(str(root / "scripts/serve-day5.py"))["make_handler"]
    broken = False

    def connect():
        if broken:
            raise RuntimeError("Sensitive connection details must not reach HTTP response")
        return psycopg.connect(os.environ["SPARKCITY_DAY5_TEST_DSN"], autocommit=True)

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bundle, connect))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/") as response:
            assert "const LIVE=true" in response.read().decode()
        with urlopen(base + "/api/snapshot") as response:
            payload = json.load(response)
            assert payload["run_id"] == bundle["run_id"]
            assert len(payload["daily"]) == len(bundle["daily"])
            assert response.headers["Cache-Control"] == "no-store"
        broken = True
        with pytest.raises(HTTPError) as failure:
            urlopen(base + "/api/snapshot")
        assert failure.value.code == 503
        message = failure.value.read().decode()
        assert "stale" in message and "Sensitive" not in message
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_database_full_local_snapshot(database, tmp_path, spark):
    """Optional real-data acceptance: no access to S2 or original replay checkpoint."""
    import psycopg
    import shutil
    from sparkcityx.day5_pipeline import replay_alert_stream
    source = os.getenv("SPARKCITY_DAY5_TEST_SNAPSHOT")
    if not source:
        pytest.skip("Set SPARKCITY_DAY5_TEST_SNAPSHOT for full local snapshot acceptance")
    source = Path(source)
    bundle = load_snapshot(source)
    publish_bundle(database, bundle)
    assert publish_bundle(database, bundle)["status"] == "unchanged"
    actual = read_publication(database)
    assert actual["daily"] == sorted(bundle["daily"], key=lambda r: (r["dataset"], r["metric"], r["day"]))
    assert actual["alerts"] == bundle["alerts"]
    for name in ("bundle.json", "manifest.json"):
        shutil.copyfile(source / name, tmp_path / name)
    shutil.copytree(source / "replay_input", tmp_path / "replay_input")

    def connect():
        return psycopg.connect(os.environ["SPARKCITY_DAY5_TEST_DSN"], autocommit=True)

    replay_alert_stream(spark, tmp_path, connect)
    replay_alert_stream(spark, tmp_path, connect)
    replayed = read_publication(database)
    assert replayed["replayed_alerts"] == len(bundle["alerts"])
    assert replayed["pending_notifications"] == len(bundle["alerts"])


def test_notebook_is_valid_python_and_database_disabled():
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/Hakeem_day5.ipynb").read_text())
    for i, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            compile(source, f"day5-cell-{i}", "exec")
    setup = "".join(notebook["cells"][1]["source"])
    assert "APPLY_DATABASE = False" in setup
    assert "INITIALIZE_SCHEMA = False" in setup
    assert "REPLAY_STREAM = False" in setup
