# SparkCity team environment

This project runs Python 3.10, PySpark 3.4.0, a Spark master, two Spark
workers, JupyterLab, and PostgreSQL in Docker. Teammates do not need to install
Python, Java, Spark, or PostgreSQL directly on their computers.

## Prerequisites

- Git
- Docker Desktop (macOS/Windows) or Docker Engine with the Compose plugin
- Make and curl (Windows users can run the commands from WSL)
- At least 8 GB of memory available to Docker

## First-time setup

```bash
git clone https://github.com/SparkCity-data/SparkCity.git
cd SparkCity
git switch dev
git pull origin dev
make setup
make start
make verify
```

The first build downloads large images and Python packages. Later starts reuse
the local Docker cache.

## Services

| Service | Address |
| --- | --- |
| JupyterLab | http://localhost:8888/lab (no local login required) |
| Spark master UI | http://localhost:9501 |
| Spark worker 1 | http://localhost:8081 |
| Spark worker 2 | http://localhost:8082 |
| Spark application UI | http://localhost:4040 while an application runs |
| PostgreSQL from the host | `localhost:9502` |

Inside Docker, connect to Spark at `spark://spark-master:7077` and PostgreSQL
at `postgres:5432`. Use relative data paths such as
`data/raw/energy_meters.csv` from Jupyter.

The host ports follow the S2 allocation. Override `SPARK_UI_PORT` or
`POSTGRES_PORT` in a local `.env` file if either port conflicts on your machine.
`HOST_BIND_ADDRESS` defaults to `127.0.0.1`; an S2 administrator can set it to
an approved network interface after restricting inbound access with the host
firewall or security group.

The checked-in passwords are local-development defaults only. Override them
without committing secrets by setting `POSTGRES_PASSWORD` and
`GRAFANA_ADMIN_PASSWORD` in a local `.env` file.

All published ports bind only to the host's loopback interface. Other machines
cannot connect directly. On a shared server, keep these bindings and use an SSH
tunnel rather than opening Jupyter, Spark, or PostgreSQL to the internet.

## Everyday commands

```bash
make start       # start core services
make status      # inspect status
make verify      # test every core service and run a Spark job
make logs        # follow logs; Ctrl-C exits
make stop        # stop services while retaining database data
make tools       # optionally start Adminer, Redis, and Grafana
```

Run `make setup` again after `requirements.txt` or `jupyter.Dockerfile`
changes. Avoid `docker compose down -v` unless you intentionally want to erase
the local PostgreSQL, Redis, and Grafana volumes.

## Feature branch workflow

```bash
git switch dev
git pull origin dev
git switch -c feature_name
git push -u origin feature_name
```

Open pull requests from feature branches into `dev`. Do not commit directly to
`main`, and do not commit passwords, SSH keys, notebook checkpoints, or
generated output.
