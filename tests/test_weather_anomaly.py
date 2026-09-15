from pyspark.sql import SparkSession

from sparkcityx.weather_anomaly import (
    WeatherAlertThresholds,
    add_multivariate_anomaly_scores,
    add_threshold_alerts,
)
from sparkcityx.weather_anomaly import (
    WeatherAlertThresholds,
    add_multivariate_anomaly_scores,
    add_threshold_alerts,
    score_isolation_forest,
)


def test_threshold_alerts_assign_severity(spark: SparkSession) -> None:
    df = spark.createDataFrame(
        [
            ("NORMAL", 60.0, 50.0, 10.0, 0.0, 1012.0),
            ("WARNING", 60.0, 50.0, 30.0, 0.0, 1012.0),
            ("CRITICAL", 100.0, 50.0, 10.0, 0.0, 970.0),
        ],
        (
            "station_id string, temperature double, humidity double, "
            "wind_speed double, precipitation double, pressure double"
        ),
    )

    thresholds = WeatherAlertThresholds(
        minimum_temperature=20.0,
        maximum_temperature=95.0,
        maximum_wind_speed=25.0,
        maximum_precipitation=1.0,
        minimum_pressure=980.0,
        maximum_pressure=1040.0,
    )

    rows = {
        row.station_id: row
        for row in add_threshold_alerts(df, thresholds).collect()
    }

    assert rows["NORMAL"].alert_count == 0
    assert rows["NORMAL"].alert_severity == "NORMAL"
    assert rows["NORMAL"].requires_investigation is False

    assert rows["WARNING"].alert_count == 1
    assert rows["WARNING"].alert_severity == "WARNING"
    assert rows["WARNING"].high_wind_alert is True

    assert rows["CRITICAL"].alert_count == 2
    assert rows["CRITICAL"].alert_severity == "CRITICAL"
    assert rows["CRITICAL"].high_temperature_alert is True
    assert rows["CRITICAL"].low_pressure_alert is True
    assert rows["CRITICAL"].requires_investigation is True
    assert rows["NORMAL"].alert_reasons == ""
    assert rows["NORMAL"].investigation_status == "NOT_REQUIRED"

    assert rows["WARNING"].alert_reasons == "HIGH_WIND"
    assert rows["WARNING"].investigation_status == "OPEN"
    assert rows["WARNING"].recommended_action == "REVIEW_READING"

    assert "HIGH_TEMPERATURE" in rows["CRITICAL"].alert_reasons
    assert "LOW_PRESSURE" in rows["CRITICAL"].alert_reasons
    assert rows["CRITICAL"].investigation_status == "OPEN"
    assert rows["CRITICAL"].recommended_action == "IMMEDIATE_REVIEW"


def test_multivariate_scoring_flags_extreme_weather(spark) -> None:
    normal_rows = [
        (
            f"WTH-{index:03d}",
            50.0 + (index % 5),
            45.0 + (index % 7),
            5.0 + (index % 3),
            0.1,
            1010.0 + (index % 4),
        )
        for index in range(100)
    ]

    extreme_row = (
        "EXTREME",
        200.0,
        100.0,
        100.0,
        10.0,
        800.0,
    )

    df = spark.createDataFrame(
        normal_rows + [extreme_row],
        (
            "station_id string, temperature double, humidity double, "
            "wind_speed double, precipitation double, pressure double"
        ),
    )

    rows = {
        row.station_id: row
        for row in add_multivariate_anomaly_scores(
            df,
            score_threshold=3.0,
        ).collect()
    }

    assert rows["EXTREME"].is_multivariate_anomaly is True
    assert rows["EXTREME"].multivariate_anomaly_score > 3.0
    assert rows["WTH-000"].multivariate_anomaly_score >= 0.0


def test_isolation_forest_flags_extreme_weather(spark) -> None:
    normal_rows = [
        (
            f"WTH-{index:03d}",
            50.0 + (index % 5),
            45.0 + (index % 7),
            5.0 + (index % 3),
            0.1 * (index % 2),
            1010.0 + (index % 4),
        )
        for index in range(100)
    ]

    extreme_row = (
        "EXTREME",
        200.0,
        100.0,
        100.0,
        10.0,
        800.0,
    )

    df = spark.createDataFrame(
        normal_rows + [extreme_row],
        (
            "station_id string, temperature double, humidity double, "
            "wind_speed double, precipitation double, pressure double"
        ),
    )

    result = score_isolation_forest(
        df,
        contamination=0.01,
        random_state=42,
    )

    rows = {
        row.station_id: row
        for row in result.scored_dataframe.collect()
    }

    assert rows["EXTREME"].is_isolation_forest_anomaly is True
    assert (
        rows["EXTREME"].isolation_forest_score
        > rows["WTH-000"].isolation_forest_score
    )