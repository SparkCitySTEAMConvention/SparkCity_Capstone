import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from sparkcityx.fiscal_forecast import (
    make_features, chronological_parts, evaluate_forecasts, predict_next_day,
    fit_candidate, predict_candidate, metrics, residual_radius,
)
from sparkcityx.fiscal_forecast_store import validate_publication, publish_forecast


def sample_daily():
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=375)
    return pd.DataFrame({"revenue": 100 + 20*np.sin(np.arange(375)/30) + 10*(dates.weekday >= 5) + rng.normal(0, 3, 375),
                         "expense": 30 + rng.normal(0, 2, 375)}, index=dates)


def test_features_exclude_target_and_future():
    daily = sample_daily()
    before = make_features(daily)
    changed = daily.copy()
    changed.iloc[100:, :] += 10000
    after = make_features(changed)
    pd.testing.assert_frame_equal(before.iloc[:101], after.iloc[:101])
    assert after.iloc[101].revenue_lag1 != before.iloc[101].revenue_lag1
    assert before.iloc[28].revenue_past28_mean == pytest.approx(daily.revenue.iloc[:28].mean())
    missing = make_features(daily.drop(daily.index[100]))
    assert pd.isna(missing.iloc[101].revenue_lag1)
    assert pd.isna(missing.iloc[107].revenue_lag7)
    assert missing.iloc[101:129].revenue_past28_mean.isna().all()


def test_partitions_are_calendar_based_and_disjoint():
    _, _, parts, audit = chronological_parts(sample_daily())
    assert audit.usable_days.tolist() == [197, 56, 37, 57]
    assert audit.calendar_days.sum() == 375
    assert sum(len(v) for v in parts.values()) == 347
    for left, right in zip(list(parts.values()), list(parts.values())[1:]):
        assert left.max() < right.min()
    with pytest.raises(ValueError, match="200"):
        chronological_parts(sample_daily().iloc[:100])


def test_models_and_calibration_do_not_learn_from_test_labels():
    daily = sample_daily()
    original, _, _, _, _ = evaluate_forecasts(daily)
    daily.iloc[318:, :] += 1000
    changed, _, _, _, _ = evaluate_forecasts(daily)
    assert original == changed


def test_saved_model_roundtrip_and_next_day_only():
    daily = sample_daily()
    artifact, _, testing, predictions, _ = evaluate_forecasts(daily)
    restored = json.loads(json.dumps(artifact, allow_nan=False))
    pd.testing.assert_frame_equal(predict_next_day(artifact, daily), predict_next_day(restored, daily))
    next_day = predict_next_day(restored, daily)
    assert next_day.target_day.eq("2026-01-11").all()
    assert next_day.horizon_days.eq(1).all()
    assert testing.rows.eq(57).all()
    assert len(predictions) == 114
    assert (next_day.lower >= 0).all()
    assert (next_day.lower <= next_day.prediction).all()
    broken = daily.copy()
    broken.iloc[-2, 0] = np.nan
    with pytest.raises(ValueError, match="history"):
        predict_next_day(restored, broken)


def test_scaling_uses_training_rows_only_and_clipping_is_consistent():
    _, x, parts, _ = chronological_parts(sample_daily())
    train = x.loc[parts["train"]]
    fitted = fit_candidate("ridge_1", train, np.ones(len(train)), "revenue")
    assert np.allclose(fitted["center"], train.mean())
    assert np.allclose(predict_candidate(fitted, x.loc[parts["test"]]), 1)
    fitted["training_mean"] = -1
    assert np.all(predict_candidate(fitted, x.loc[parts["test"]]) == 0)


def test_metrics_and_calibration_checks():
    perfect = metrics([1, 2, 3], [1, 2, 3])
    assert perfect["rmse"] == 0 and perfect["r2"] == 1
    assert metrics([1, 1], [1, 1])["r2"] is None
    assert residual_radius(np.arange(30), np.zeros(30)) == 27
    with pytest.raises(ValueError):
        residual_radius([1], [0])
    with pytest.raises(ValueError):
        metrics([1, 2], [1])
    with pytest.raises(ValueError):
        metrics([np.inf], [1])


def publication_fixture():
    daily = sample_daily()
    artifact, _, testing, predictions, _ = evaluate_forecasts(daily)
    return {"status": "complete", "run_id": "fixture", "provenance": {"source": "test"},
            "artifact": artifact, "metrics": json.loads(testing.to_json(orient="records")),
            "predictions": json.loads(predictions.to_json(orient="records")),
            "next_day": json.loads(predict_next_day(artifact, daily).to_json(orient="records"))}


@pytest.mark.parametrize("bad", ["status", "bounds", "date", "duplicate", "actual", "target"])
def test_bad_publication_fails_before_database(bad):
    bundle = publication_fixture()
    if bad == "status": bundle["status"] = "running"
    if bad == "bounds": bundle["next_day"][0]["lower"] = float("inf")
    if bad == "date": bundle["next_day"][0]["target_day"] = "2027-04-07"
    if bad == "duplicate": bundle["predictions"].append(bundle["predictions"][0])
    if bad == "actual": bundle["predictions"][0]["actual"] = -1
    if bad == "target": bundle["next_day"][0]["target"] = "fiscal_total"
    connection = MagicMock()
    with pytest.raises(ValueError):
        publish_forecast(connection, bundle)
    connection.transaction.assert_not_called()


def test_publication_validation_and_notebook_syntax():
    bundle = publication_fixture()
    sha, rows = validate_publication(bundle)
    assert len(sha) == 64 and len(rows) == 116
    root = Path(__file__).resolve().parents[1]
    nb = json.loads((root / "notebooks/Hakeem_fiscal_model.ipynb").read_text())
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"fiscal-model-cell-{index}", "exec")
    assert "APPLY_DATABASE = False" in "".join(nb["cells"][1]["source"])


def test_spark_model_roundtrip(spark, tmp_path):
    daily = sample_daily()
    data, features, parts, _ = chronological_parts(daily)
    model = fit_candidate("spark_random_forest", features.loc[parts["train"]],
                          data.loc[parts["train"], "revenue"], "revenue", spark=spark, model_directory=tmp_path)
    restored = json.loads(json.dumps(model))
    a = predict_candidate(model, features.loc[parts["test"]], spark=spark, model_directory=tmp_path)
    b = predict_candidate(restored, features.loc[parts["test"]], spark=spark, model_directory=tmp_path)
    assert len(a) == 57 and np.allclose(a, b)


@pytest.fixture
def fiscal_database():
    import os
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    dsn = os.getenv("SPARKCITY_DAY5_TEST_DSN")
    if not dsn:
        pytest.skip("Requires the explicitly isolated Docker test database")
    settings = conninfo_to_dict(dsn)
    if not (settings.get("host") == "127.0.0.1" and settings.get("port") == "55439"
            and settings.get("dbname") == "sparkcity_day5_test"):
        pytest.fail("Refusing any database other than the isolated local test database")
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as c:
            c.execute("SELECT to_regnamespace('sparkcity_analytics_hakeem')")
            if c.fetchone()[0] is not None:
                pytest.fail("Schema already exists; refusing to overwrite it")
            root = Path(__file__).resolve().parents[1]
            c.execute((root / "sql/003_fiscal_forecasts.sql").read_text())
        try:
            yield connection
        finally:
            # Only the schema created above, in this explicitly isolated test database.
            connection.execute("DROP SCHEMA sparkcity_analytics_hakeem CASCADE")


def test_database_fiscal_publish_retry_conflict(fiscal_database):
    bundle = publication_fixture()
    assert publish_forecast(fiscal_database, bundle)["status"] == "published"
    assert publish_forecast(fiscal_database, bundle)["status"] == "unchanged"
    row = fiscal_database.execute("SELECT count(*) FROM sparkcity_analytics_hakeem.fiscal_prediction").fetchone()
    assert row[0] == 116
    changed = copy.deepcopy(bundle)
    changed["provenance"]["source"] = "changed"
    with pytest.raises(ValueError, match="different content"):
        publish_forecast(fiscal_database, changed)
    changed["run_id"] = "second"
    publish_forecast(fiscal_database, changed)
    publish_forecast(fiscal_database, bundle)
    assert fiscal_database.execute("SELECT run_id FROM sparkcity_analytics_hakeem.fiscal_forecast_publication").fetchone()[0] == "second"


def test_database_fiscal_atomic_rollback(fiscal_database):
    import psycopg
    fiscal_database.execute("ALTER TABLE sparkcity_analytics_hakeem.fiscal_prediction "
                            "ADD CONSTRAINT test_reject_expense CHECK(target='revenue')")
    with pytest.raises(psycopg.Error):
        publish_forecast(fiscal_database, publication_fixture())
    for table in ("fiscal_forecast_run", "fiscal_prediction", "fiscal_forecast_publication"):
        assert fiscal_database.execute(f"SELECT count(*) FROM sparkcity_analytics_hakeem.{table}").fetchone()[0] == 0


def test_database_full_fiscal_snapshot(fiscal_database):
    import os
    path = os.getenv("SPARKCITY_FISCAL_TEST_SNAPSHOT")
    if not path:
        pytest.skip("Set SPARKCITY_FISCAL_TEST_SNAPSHOT for actual snapshot acceptance")
    bundle = json.loads((Path(path) / "publication.json").read_text())
    result = publish_forecast(fiscal_database, bundle)
    assert result["prediction_rows"] == len(bundle["predictions"]) + 2
    assert publish_forecast(fiscal_database, bundle)["status"] == "unchanged"
    stored = fiscal_database.execute("SELECT model_artifact FROM sparkcity_analytics_hakeem.fiscal_forecast_run").fetchone()[0]
    assert stored == bundle["artifact"]
    actual = fiscal_database.execute("SELECT target,prediction,lower_bound,upper_bound FROM "
        "sparkcity_analytics_hakeem.fiscal_prediction WHERE prediction_kind='next_day' ORDER BY target").fetchall()
    expected = sorted([(r["target"], r["prediction"], r["lower"], r["upper"]) for r in bundle["next_day"]])
    assert actual == expected
