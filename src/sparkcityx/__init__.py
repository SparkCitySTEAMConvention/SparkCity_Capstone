"""Shared utilities for the SparkCity capstone project."""

from .data_quality import get_validation_config, validate_dataframe
from .database import check_database_connection, connect_database
from .database_load import load_dataframe
from .loaders import load_dataset
from .transforms import add_occupancy_rate, add_traffic_anomaly_flags

__all__ = [
    "add_occupancy_rate",
    "add_traffic_anomaly_flags",
    "check_database_connection",
    "connect_database",
    "get_validation_config",
    "load_dataset",
    "load_dataframe",
    "validate_dataframe",
]


def main() -> None:
    print("SparkCity shared utilities are installed.")
