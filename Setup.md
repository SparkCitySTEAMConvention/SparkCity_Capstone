## Local Setup

### Prerequisites

Before running New York Digital City locally, make sure you have:

- Python 3.13+
- PostgreSQL
- Git
- A virtual environment
- Access to the New York Digital City database credentials

---

### 1. Clone the Repository

```bash
git clone https://github.com/SparkCitySTEAMConvention/SparkCity_Capstone.git
cd SparkCity_Capstone
```

If you already cloned the repository, navigate to the project directory:

```bash
cd ~/Projects/SparkCity_Capstone
```

---

### 2. Create and Activate a Virtual Environment

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

Your terminal should now show `(.venv)` before the command prompt.

---

### 3. Install Project Dependencies

Install the project and its dependencies:

```bash
pip install -e .
```

If development dependencies are configured separately in the project, install those as required before running the test suite.

---

### 4. Configure the Database Connection

The application expects the PostgreSQL connection string in the `DATABASE_URL` environment variable.

Create the local environment file from the example:

```bash
cp .env.example secrets/.env
```

Add the instructor-provided PostgreSQL credentials to:

```text
secrets/.env
```

Do not commit `secrets/.env` or database credentials to GitHub.

Before running the application, load the environment variables into the current terminal session:

```bash
set -a
source secrets/.env
set +a
```

---

### 5. Verify PostgreSQL with psql

Make sure PostgreSQL is available:

```bash
psql --version
```

To connect using the `DATABASE_URL` stored in `secrets/.env`, first load the environment variables:

```bash
set -a
source secrets/.env
set +a
```

Then start `psql`:

```bash
psql "$DATABASE_URL"
```

Once connected, you can verify the database connection with:

```sql
\conninfo
```

List the available tables:

```sql
\dt
```

Exit `psql` with:

```sql
\q
```

---

### 6. Run the SparkCity Dashboard

From the project root, make sure your virtual environment is active and the database environment variables have been loaded:

```bash
source .venv/bin/activate

set -a
source secrets/.env
set +a
```

Start the Mobility & Traffic Streamlit page:

```bash
PYTHONPATH=src streamlit run dashboard/pages/mobility_traffic.py
```

Streamlit will display a local URL in the terminal, typically:

```text
http://localhost:8501
```

Open that address in your browser to view the dashboard.

Press `Ctrl+C` in the terminal to stop the Streamlit server.

---

### 7. Run the Tests

Before pushing code, run the complete test suite from the project root:

```bash
pytest
```

A successful test run should complete without failures.

---

## Quick Start

For returning developers who have already completed the initial setup:

```bash
cd ~/Projects/SparkCity_Capstone
source .venv/bin/activate
set -a
source secrets/.env
set +a
PYTHONPATH=src streamlit run dashboard/pages/mobility_traffic.py
```

To open PostgreSQL instead:

```bash
set -a
source secrets/.env
set +a
psql "$DATABASE_URL"
```