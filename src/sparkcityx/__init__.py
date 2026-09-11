"""Shared utilities for the SparkCity capstone project."""

from .data_quality import get_validation_config, validate_dataframe
from .database import check_database_connection, connect_database
from .loaders import load_dataset

__all__ = [
    "check_database_connection",
    "connect_database",
    "get_validation_config",
    "load_dataset",
    "validate_dataframe",
]


def main() -> None:
    print("SparkCity shared utilities are installed.")
