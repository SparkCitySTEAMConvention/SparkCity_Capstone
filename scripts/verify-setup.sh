#!/usr/bin/env bash
set -eu

failed=0

check_url() {
  name="$1"
  url="$2"
  if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
    echo "OK   $name ($url)"
  else
    echo "FAIL $name ($url)"
    failed=1
  fi
}

check_url "Spark master" "http://localhost:8080"
check_url "Spark worker 1" "http://localhost:8081"
check_url "Spark worker 2" "http://localhost:8082"
check_url "JupyterLab" "http://localhost:8888"

if docker compose exec -T postgres pg_isready -U postgres -d smartcity >/dev/null; then
  echo "OK   PostgreSQL (localhost:5432)"
else
  echo "FAIL PostgreSQL (localhost:5432)"
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
  'from pyspark.sql import SparkSession; s=SparkSession.builder.getOrCreate(); assert s.range(1, 101).count() == 100; print("OK   Distributed Spark job"); s.stop()'; then
  :
else
  echo "FAIL Distributed Spark job"
  failed=1
fi

exit "$failed"
