# Local Setup

These instructions use the repository's `uv` environment and launch the full Streamlit application. Start in the repository root.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Java 17 or 21 for PySpark workflows
- PostgreSQL credentials only for database-backed dashboard views or database scripts

## Install

```bash
uv python install 3.13
uv sync --dev
```

`uv` creates and manages the project environment from `pyproject.toml` and `uv.lock`.

## Run the dashboard

```bash
uv run streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit, usually <http://localhost:8501>. Stop the server with `Ctrl+C`.

The app can launch without database credentials. Environment history and Capacity & Utilization features that read shared PostgreSQL data require an approved database connection. Other views may use local project data or external public data sources.

## Optional: configure PostgreSQL

Copy the example file and add the credentials provided for your project environment:

```bash
mkdir -p secrets
cp -n .env.example secrets/.env
```

Edit `secrets/.env` and replace the placeholder values. The application loads this file locally. Never commit it, share it publicly, or paste credentials into notebooks; `secrets/` is ignored by Git.

Check the connection without reading or changing application data:

```bash
uv run python scripts/check-database.py
```

The shared connection helper requires encrypted SSL. Use the approved database endpoint and SSL settings; the checked-in example uses `sslmode=require`. Do not create schemas, load data, or write to shared tables without explicit team approval. See [Day 5 workflow](docs/day5_workflow.md) for the reviewed pipeline and database operations.

## Tests

Run the project test suite:

```bash
uv run pytest
```

Database integration tests require a separately configured, isolated test database. Never point integration tests at the shared project database.
