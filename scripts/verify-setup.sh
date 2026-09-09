#!/usr/bin/env bash
set -eu

failed=0
spark_ui_port="${SPARK_UI_PORT:-9501}"
postgres_port="${POSTGRES_PORT:-9502}"

check_url() {
  name="$1"
  url="$2"
  attempts=12

  while [ "$attempts" -gt 0 ]; do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
      echo "OK   $name ($url)"
      return
    fi
    attempts=$((attempts - 1))
    [ "$attempts" -eq 0 ] || sleep 2
  done

  echo "FAIL $name ($url) after waiting for startup"
  failed=1
}

check_url "Spark master" "http://localhost:${spark_ui_port}"
check_url "Spark worker 1" "http://localhost:8081"
check_url "Spark worker 2" "http://localhost:8082"
check_url "JupyterLab" "http://localhost:8888"

if docker compose exec -T postgres pg_isready -U postgres -d smartcity >/dev/null; then
  echo "OK   PostgreSQL (localhost:${postgres_port})"
else
  echo "FAIL PostgreSQL (localhost:${postgres_port})"
  failed=1
fi

if docker compose exec -T jupyter python -c \
  'from pathlib import Path; required=["air_quality.json", "city_zones.csv", "energy_meters.csv", "traffic_sensors.csv", "weather_data.json"]; assert all((Path("data/raw") / name).is_file() for name in required); print("OK   Raw datasets mounted")'; then
  :
else
  echo "FAIL Raw datasets mounted"
  failed=1
fi

if docker compose exec -T jupyter python -c \
  'from pyspark.sql import SparkSession; s=SparkSession.builder.getOrCreate(); assert s.read.option("header", True).csv("file:///home/jovyan/work/data/raw/energy_meters.csv").count() > 0; print("OK   Distributed Spark dataset read"); s.stop()'; then
  :
else
  echo "FAIL Distributed Spark dataset read"
  failed=1
fi

exit "$failed"
