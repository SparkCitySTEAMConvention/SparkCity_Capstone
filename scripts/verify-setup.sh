#!/usr/bin/env bash
set -eu

failed=0

# Check container state before probing ports: another local process may answer
# on a port that Compose failed to bind.
running_services=$(docker compose ps --status running --services)
for service in spark-master spark-worker-1 spark-worker-2 postgres jupyter; do
  if ! printf '%s\n' "$running_services" | grep -qx "$service"; then
    echo "FAIL $service is not running (see docker compose logs $service)"
    failed=1
  fi
done
[ "$failed" -eq 0 ] || exit "$failed"

# Read actual published ports so shell and .env overrides are both respected.
service_address() {
  docker compose port "$1" "$2"
}

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

check_url "Spark master" "http://$(service_address spark-master 8080)"
check_url "Spark worker 1" "http://$(service_address spark-worker-1 8081)"
check_url "Spark worker 2" "http://$(service_address spark-worker-2 8081)"
check_url "JupyterLab" "http://$(service_address jupyter 8888)/lab"

if docker compose exec -T postgres pg_isready -U postgres -d smartcity >/dev/null; then
  echo "OK   PostgreSQL ($(service_address postgres 5432))"
else
  echo "FAIL PostgreSQL ($(service_address postgres 5432))"
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
