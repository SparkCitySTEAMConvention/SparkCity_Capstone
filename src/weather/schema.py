"""Schema definition for SparkCity weather-station data."""

from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


WEATHER_SCHEMA = StructType(
    [
        StructField("station_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("location_lat", DoubleType(), False),
        StructField("location_lon", DoubleType(), False),
        StructField("temperature", DoubleType(), True),
        StructField("humidity", DoubleType(), True),
        StructField("wind_speed", DoubleType(), True),
        StructField("wind_direction", DoubleType(), True),
        StructField("precipitation", DoubleType(), True),
        StructField("pressure", DoubleType(), True),
    ]
)


WEATHER_COLUMNS = [
    field.name for field in WEATHER_SCHEMA.fields
]