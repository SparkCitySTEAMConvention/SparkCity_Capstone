#!/usr/bin/env python3
"""Generate synthetic Smart City IoT datasets for local development."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_RECORDS = 3000
DEFAULT_SEED = 42
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

CITY_BOUNDS = {
    "lat_min": 40.6800,
    "lat_max": 40.8400,
    "lon_min": -74.0500,
    "lon_max": -73.8800,
}

ROAD_TYPES = ["arterial", "highway", "residential", "downtown", "school_zone"]
BUILDING_TYPES = ["residential", "commercial", "industrial", "municipal", "mixed_use"]
ZONE_TYPES = ["residential", "commercial", "industrial", "mixed_use", "park", "campus"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        type=int,
        default=DEFAULT_RECORDS,
        help=f"Rows to generate for each dataset (default: {DEFAULT_RECORDS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic output (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where datasets will be written (default: {DEFAULT_OUTPUT_DIR}).",
    )
    return parser.parse_args()


def build_zones(record_count: int, rng: random.Random) -> list[dict[str, object]]:
    columns = math.ceil(math.sqrt(record_count))
    rows = math.ceil(record_count / columns)
    lat_step = (CITY_BOUNDS["lat_max"] - CITY_BOUNDS["lat_min"]) / rows
    lon_step = (CITY_BOUNDS["lon_max"] - CITY_BOUNDS["lon_min"]) / columns
    populations = {
        "residential": (2000, 12000),
        "commercial": (500, 4000),
        "industrial": (100, 1200),
        "mixed_use": (1500, 8000),
        "park": (0, 250),
        "campus": (800, 6000),
    }

    zones: list[dict[str, object]] = []
    for index in range(record_count):
        row = index // columns
        column = index % columns
        zone_type = ZONE_TYPES[index % len(ZONE_TYPES)]
        population_min, population_max = populations[zone_type]
        lat_min = CITY_BOUNDS["lat_min"] + row * lat_step
        lon_min = CITY_BOUNDS["lon_min"] + column * lon_step
        zones.append(
            {
                "zone_id": f"ZONE-{index + 1:04d}",
                "zone_name": f"{zone_type.replace('_', ' ').title()} Zone {index + 1:04d}",
                "zone_type": zone_type,
                "lat_min": round(lat_min, 6),
                "lat_max": round(lat_min + lat_step, 6),
                "lon_min": round(lon_min, 6),
                "lon_max": round(lon_min + lon_step, 6),
                "population": rng.randint(population_min, population_max),
            }
        )
    return zones


def random_point(zone: dict[str, object], rng: random.Random) -> tuple[float, float]:
    lat = rng.uniform(float(zone["lat_min"]), float(zone["lat_max"]))
    lon = rng.uniform(float(zone["lon_min"]), float(zone["lon_max"]))
    return round(lat, 6), round(lon, 6)


def build_traffic_rows(
    record_count: int, zones: list[dict[str, object]], rng: random.Random
) -> list[dict[str, object]]:
    sensor_count = max(180, record_count // 12)
    sensors = [f"TRF-{index + 1:04d}" for index in range(sensor_count)]
    start = datetime(2025, 1, 1, 0, 0, 0)
    speed_limits = {
        "arterial": 45.0,
        "highway": 65.0,
        "residential": 25.0,
        "downtown": 20.0,
        "school_zone": 15.0,
    }

    rows: list[dict[str, object]] = []
    for index in range(record_count):
        timestamp = start + timedelta(minutes=5 * index)
        zone = zones[index % len(zones)]
        road_type = ROAD_TYPES[(index + rng.randint(0, len(ROAD_TYPES) - 1)) % len(ROAD_TYPES)]
        lat, lon = random_point(zone, rng)
        rush_multiplier = 1.55 if timestamp.hour in {7, 8, 16, 17, 18} else 1.0
        weather_drag = 0.75 if timestamp.day % 10 == 0 else 1.0
        vehicle_count = int(rng.randint(20, 120) * rush_multiplier * weather_drag)
        free_flow_speed = speed_limits[road_type]
        slowdown = min(vehicle_count / 160, 0.65)
        avg_speed = round(max(free_flow_speed * (1 - slowdown) + rng.uniform(-3, 3), 5.0), 2)
        if vehicle_count > 130 or avg_speed < free_flow_speed * 0.45:
            congestion = "high"
        elif vehicle_count > 80 or avg_speed < free_flow_speed * 0.7:
            congestion = "medium"
        else:
            congestion = "low"

        rows.append(
            {
                "sensor_id": sensors[index % sensor_count],
                "timestamp": timestamp,
                "location_lat": lat,
                "location_lon": lon,
                "vehicle_count": vehicle_count,
                "avg_speed": avg_speed,
                "congestion_level": congestion,
                "road_type": road_type,
            }
        )
    return rows


def build_air_quality_rows(
    record_count: int, zones: list[dict[str, object]], rng: random.Random
) -> list[dict[str, object]]:
    sensor_count = max(120, record_count // 20)
    sensors = [f"AIR-{index + 1:04d}" for index in range(sensor_count)]
    start = datetime(2025, 1, 1, 0, 0, 0)

    rows: list[dict[str, object]] = []
    for index in range(record_count):
        timestamp = start + timedelta(minutes=15 * index)
        zone = zones[(index * 3) % len(zones)]
        lat, lon = random_point(zone, rng)
        zone_type = str(zone["zone_type"])
        pollution_boost = {
            "industrial": 1.45,
            "commercial": 1.15,
            "mixed_use": 1.05,
            "residential": 0.95,
            "campus": 0.9,
            "park": 0.75,
        }[zone_type]
        temperature = round(48 + 18 * math.sin(index / 150) + rng.uniform(-4, 4), 2)
        humidity = round(45 + 20 * math.cos(index / 130) + rng.uniform(-6, 6), 2)
        pm25 = round(max(rng.uniform(7, 35) * pollution_boost, 1.0), 2)
        pm10 = round(max(pm25 * rng.uniform(1.1, 1.8), pm25 + 1), 2)
        no2 = round(max(rng.uniform(8, 45) * pollution_boost, 1.0), 2)
        co = round(max(rng.uniform(0.1, 1.4) * pollution_boost, 0.05), 3)

        rows.append(
            {
                "sensor_id": sensors[index % sensor_count],
                "timestamp": timestamp,
                "location_lat": lat,
                "location_lon": lon,
                "pm25": pm25,
                "pm10": pm10,
                "no2": no2,
                "co": co,
                "temperature": temperature,
                "humidity": humidity,
            }
        )
    return rows


def build_weather_rows(
    record_count: int, zones: list[dict[str, object]], rng: random.Random
) -> list[dict[str, object]]:
    station_count = max(90, record_count // 30)
    stations = [f"WTH-{index + 1:04d}" for index in range(station_count)]
    start = datetime(2025, 1, 1, 0, 0, 0)

    rows: list[dict[str, object]] = []
    for index in range(record_count):
        timestamp = start + timedelta(minutes=30 * index)
        zone = zones[(index * 5) % len(zones)]
        lat, lon = random_point(zone, rng)
        seasonal = math.sin(index / 90)
        temperature = round(52 + 16 * seasonal + rng.uniform(-3, 3), 2)
        humidity = round(58 - 12 * seasonal + rng.uniform(-5, 5), 2)
        wind_speed = round(max(rng.uniform(2, 18) + abs(math.cos(index / 40)) * 6, 0.2), 2)
        rows.append(
            {
                "station_id": stations[index % station_count],
                "timestamp": timestamp,
                "location_lat": lat,
                "location_lon": lon,
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": round(rng.uniform(0, 360), 2),
                "precipitation": round(max(rng.gauss(0.08, 0.18), 0.0), 3),
                "pressure": round(1012 + rng.uniform(-10, 10), 2),
            }
        )
    return rows


def build_energy_rows(
    record_count: int, zones: list[dict[str, object]], rng: random.Random
) -> list[dict[str, object]]:
    meter_count = max(150, record_count // 15)
    meters = [f"ENG-{index + 1:04d}" for index in range(meter_count)]
    start = datetime(2025, 1, 1, 0, 0, 0)

    load_bases = {
        "residential": 18.0,
        "commercial": 42.0,
        "industrial": 75.0,
        "municipal": 35.0,
        "mixed_use": 55.0,
    }

    rows: list[dict[str, object]] = []
    for index in range(record_count):
        timestamp = start + timedelta(minutes=10 * index)
        zone = zones[(index * 7) % len(zones)]
        building_type = BUILDING_TYPES[(index + rng.randint(0, len(BUILDING_TYPES) - 1)) % len(BUILDING_TYPES)]
        lat, lon = random_point(zone, rng)
        demand_wave = 1.2 if timestamp.hour in {6, 7, 8, 17, 18, 19} else 0.9
        base_load = load_bases[building_type] * demand_wave
        power_consumption = round(max(rng.gauss(base_load, base_load * 0.18), 2.5), 2)
        voltage = round(rng.uniform(114, 126), 2)
        current = round(power_consumption * 1000 / max(voltage, 1) / 10, 2)
        power_factor = round(min(max(rng.uniform(0.82, 0.99), 0.7), 1.0), 2)

        rows.append(
            {
                "meter_id": meters[index % meter_count],
                "timestamp": timestamp,
                "building_type": building_type,
                "location_lat": lat,
                "location_lon": lon,
                "power_consumption": power_consumption,
                "voltage": voltage,
                "current": current,
                "power_factor": power_factor,
            }
        )
    return rows


def sanitize_for_text(value: object) -> object:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def write_csv_file(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows available for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: sanitize_for_text(value) for key, value in row.items()})


def write_json_lines(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({key: sanitize_for_text(value) for key, value in row.items()}))
            handle.write("\n")


def write_parquet_file(path: Path, rows: list[dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist(rows), path)
        return "pyarrow"
    except (ImportError, ModuleNotFoundError):
        pass

    try:
        import pandas as pd

        pd.DataFrame(rows).to_parquet(path, index=False)
        return "pandas"
    except (ImportError, ModuleNotFoundError, ValueError):
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder.master("local[1]").appName("sparkcity-data-generator").getOrCreate()
            spark.sparkContext.setLogLevel("ERROR")
            spark.createDataFrame(rows).write.mode("overwrite").parquet(str(path))
            spark.stop()
            return "pyspark"
        except Exception as exc:  # pragma: no cover - fallback safety
            raise RuntimeError(
                "Writing weather_data.parquet requires pandas with a parquet engine "
                "or a working pyspark installation."
            ) from exc


def main() -> None:
    args = parse_args()
    if args.records <= 0:
        raise SystemExit("--records must be greater than zero.")

    rng = random.Random(args.seed)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    zones = build_zones(args.records, rng)
    traffic_rows = build_traffic_rows(args.records, zones, rng)
    air_quality_rows = build_air_quality_rows(args.records, zones, rng)
    weather_rows = build_weather_rows(args.records, zones, rng)
    energy_rows = build_energy_rows(args.records, zones, rng)

    write_csv_file(output_dir / "city_zones.csv", zones)
    write_csv_file(output_dir / "traffic_sensors.csv", traffic_rows)
    write_csv_file(output_dir / "energy_meters.csv", energy_rows)
    write_json_lines(output_dir / "air_quality.json", air_quality_rows)
    parquet_engine = write_parquet_file(output_dir / "weather_data.parquet", weather_rows)

    print(f"Wrote {len(zones)} rows to {output_dir / 'city_zones.csv'}")
    print(f"Wrote {len(traffic_rows)} rows to {output_dir / 'traffic_sensors.csv'}")
    print(f"Wrote {len(energy_rows)} rows to {output_dir / 'energy_meters.csv'}")
    print(f"Wrote {len(air_quality_rows)} rows to {output_dir / 'air_quality.json'}")
    print(
        f"Wrote {len(weather_rows)} rows to {output_dir / 'weather_data.parquet'} "
        f"using {parquet_engine}"
    )


if __name__ == "__main__":
    main()
