"""Shared utilities for the SparkCity capstone project."""

from .data_quality import get_validation_config, validate_dataframe
from .database import check_database_connection, connect_database
from .database_load import load_dataframe
from .loaders import load_dataset
from .weather_features import (
    add_weather_interaction_features,
    add_weather_rolling_features,
    add_weather_time_features,
    aggregate_daily_weather,
    aggregate_hourly_weather,
    aggregate_zone_hourly_weather,
    map_weather_to_zones,
)
from .weather_anomaly import (
    IsolationForestResult,
    WeatherAlertThresholds,
    add_multivariate_anomaly_scores,
    add_threshold_alerts,
    score_isolation_forest,
)
from .weather_model import (
    WeatherForecastResult,
    train_temperature_forecaster,
)



__all__ = [
    "check_database_connection",
    "connect_database",
    "get_validation_config",
    "load_dataset",
    "load_dataframe",
    "validate_dataframe",
    "add_weather_interaction_features",
    "add_weather_rolling_features",
    "add_weather_time_features",
    "aggregate_daily_weather",
    "aggregate_hourly_weather",
    "aggregate_zone_hourly_weather",
    "map_weather_to_zones",
    "WeatherAlertThresholds",
    "add_multivariate_anomaly_scores",
    "add_threshold_alerts",
    "WeatherForecastResult",
    "train_temperature_forecaster",
    "IsolationForestResult",
    "score_isolation_forest",
]


def main() -> None:
    print("SparkCity shared utilities are installed.")
