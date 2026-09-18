# Day 5 — database integration and dashboard

Run `notebooks/Hakeem_day5.ipynb` using the project `.venv` after `uv sync --dev`.
Default **Run All does not connect to S2**. It reads completed Day 4/3 snapshots,
checks lineage and hashes, uses Spark to aggregate observations, and writes a new
`data/processed/day5/<run>` directory. The shared validator and raw loader are unchanged.

## What is implemented

| Requirement | Implementation and boundary |
|---|---|
| Analytics schema | Date and metric dimensions, versioned daily facts, alert facts, run provenance and atomic publication pointer; `sql/002_day5_analytics.sql` |
| Spark/PostgreSQL batch integration | Spark aggregates → validated compact driver results → psycopg transaction. Appropriate for these small aggregates; not a distributed JDBC bulk loader. |
| Streaming writes and upserts | Bounded Spark Structured Streaming historical-alert replay, `foreachBatch`, persistent checkpoint, batch ledger, content-checked alert IDs and conflict-safe notification inserts. Not a live sensor feed or new model scoring. |
| Interactive dashboard | Six dataset/metric selectors, calendar filters, SVG chart, daily/alert drill-down, filtered download. Database-backed preview polls every 15 seconds and reports failures as stale. |
| Alert notifications | Durable pending outbox and opt-in browser notices while the page is open. No email/SMS worker; browser notices do not acknowledge delivery of individual outbox events. |
| Automation/recovery | Headless runner, nonzero exit on failure, running/failed/complete manifests, safe same-snapshot publication retry, persistent stream checkpoints. Scheduler installation is explicitly opt-in. |
| Retention | Explicit preview/apply function for unpublished analytics snapshots older than 90 days. Published snapshot preserved; no raw data deletion. Outbox/stream history retained pending team policy. |

This is a local integration implementation, **not a production-readiness certification**.
S2 privileges, deployment authentication/TLS, monitoring ownership, capacity, backup/restore,
freshness SLA, alert recipients, and live-stream source must be approved and tested separately.
The loopback HTTP server is a development preview, not an internet-facing production server.

## Schema and correction policy

`sparkcity_analytics_hakeem` is isolated from the team's `sparkcity` tables.
Daily fact grain: **run × dataset × metric × calendar day**. Counts describe input
observations and distinct sensor identifiers, not stable physical locations.
The composite primary key supports the dashboard's run/dataset/metric/date filters;
the alert index supports run/dataset/time filtering. Verify query plans on deployment
data rather than claiming these indexes are universally optimal.

A run ID is immutable: identical retry is a no-op; changed payload under the same ID
is rejected. Corrected inputs require a new validated snapshot. The active publication
pointer is upserted in the same transaction as all facts. Readers use a consistent
transaction. Retrying an old, already-published run does not roll the pointer backward.
Explicitly publishing a *new* snapshot built from older inputs is possible; the operator
must review lineage before choosing it. No raw records are updated.

## Local build and optional S2 publication

From the repository root:

```bash
uv run python scripts/run-day5.py --day4-run 20260914T205935811311Z
```

Open the printed run's `dashboard.html` for the self-contained offline view.
`manifest.json` means the **local** snapshot is complete, not that it is in S2.
The fiscal handoff is `fiscal_daily.csv`; revenue minus expense is an observation-level
difference in unconfirmed source currency units, not convention profit.

After team approval of schema name, permissions, and policy, set `DATABASE_URL` in the
ignored `secrets/.env` (never in the notebook). Replace `<run>` below with an actual Day 5 run:

```bash
uv run python scripts/run-day5.py --snapshot data/processed/day5/<run> --apply --initialize-schema
uv run python scripts/run-day5.py --snapshot data/processed/day5/<run> --apply --replay
uv run python scripts/serve-day5.py --snapshot data/processed/day5/<run>
```

The first command performs DDL and writes; do not run it merely to inspect connectivity.
Keep schema setup separate from recurring operation. Use the shared SSL-enforcing
connection helper. Give the dashboard a separate SELECT-only account using an environment
override; environment values take precedence over `.env`. Credentials never enter HTML.
Publication uses bounded lock/statement waits. Concurrent publication uses an advisory lock.
The stream replay has a separate transaction lock and never marks external notifications delivered.

## Scheduling (not installed automatically)

Schedule the headless runner, not notebook UI cells. A single scheduler worker must prevent
overlapping executions. Pin the source for a reproducible demonstration; choose a reviewed
new Day 4 snapshot when inputs change. A schedule does not itself rerun Days 1–4 or obtain new data.

For macOS, configure a LaunchAgent with `StartInterval = 3600`, `WorkingDirectory` set to
the repository, and absolute `ProgramArguments`:

```text
/Users/hakeem/Projects/SparkCity_Capstone/.venv/bin/python
/Users/hakeem/Projects/SparkCity_Capstone/scripts/run-day5.py
--day4-run
20260914T205935811311Z
```

Set separate `StandardOutPath`/`StandardErrorPath` in an existing, access-controlled log
directory; inspect exit status and the newest manifest after each run. Use one LaunchAgent
label to avoid overlapping copies. Default schedule above only builds locally. Add `--apply`
only after review; do not schedule `--initialize-schema`. Prefer a fixed `--snapshot ... --apply`
for publication retries rather than rebuilding a new version on every retry. Pinning a
snapshot republishes no new data. Rotate logs and agree on retention before unattended use.

The ready-to-review template is `config/com.sparkcity.hakeem.day5.plist`.
To install it **only when wanted**, ensure `data/processed/day5` exists, review paths,
then copy it to `~/Library/LaunchAgents/` and run
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sparkcity.hakeem.day5.plist`.
To stop scheduling, use `launchctl bootout gui/$(id -u)/com.sparkcity.hakeem.day5`.
These commands are documentation, not actions performed by this notebook. `StartInterval`
does not guarantee execution while the machine is asleep or the user is logged out.

## Failure and retention procedures

- Missing/changed input or invalid aggregate: stop before database publication; retain failed
  run directory for investigation. Correct source and build a new run.
- Database interruption: the transaction rolls back or may have committed before the client
  lost the acknowledgement. Retry the **same** completed snapshot; its digest makes this safe.
- Stream interruption: restart the same replay command with the existing checkpoint. The
  database ledger and alert IDs also deduplicate retries if acknowledgement was lost.
- Changed content under an existing run, batch, or alert ID: reject and investigate; no silent overwrite.
- Dashboard outage: retain last successful display with an explicit stale banner. Historical
  source coverage is shown separately from connection/polling freshness.
- `retention_candidates(connection)` previews old unpublished runs.
  `retention_candidates(connection, keep_days=90, apply=True)` deletes those runs and their
  cascading facts. Review the candidate list and backup first; no automatic cleanup is scheduled.
  Database backups are required to recover applied deletions. Dimension rows are retained.

## Fiscal convention-date analysis comes next

First clarify whether the question is **detect a past event** or **choose a future window**.
Confirm currency, accounting period, timezone, and whether records represent flows or
repeated snapshots. Check sensor coverage/composition, weekday/seasonality, anomalous days,
and consecutive multi-day windows. Use held-out checks and other datasets to corroborate
patterns; preserve uncertainty. The current synthetic data and the 27 assumption-based
scenarios alone cannot establish a real convention date or causal financial effect.

## Verification recorded September 17, 2026

- Executed every notebook code cell in order with default local-only settings.
- Source Day 4: `20260914T205935811311Z`; verified its Day 3 lineage and input hashes.
- Local notebook output: `20260917T041236367989Z`; 216,000 input observations,
  8,000 daily metric records, 458 review alerts, and 375 fiscal observation days.
- Full pytest suite: **70 passed**, including the five reference and seven generated
  dataset cases, isolated PostgreSQL transactions, concurrent publication, rollback,
  protected retention, Spark checkpoint restart, notification deduplication, full-snapshot
  read-back, and dashboard HTTP success/failure behavior.
- JavaScript DOM smoke test: six datasets, 20 metrics, empty-date range, reset, download,
  and offline status. This is not a visual browser or accessibility certification.
- LaunchAgent plist syntax and `git diff --check` passed.
- PostgreSQL testing used a disposable Docker container, now stopped and removed.
  No S2 connection, shared table write, scheduler installation, email or SMS occurred.
- Local setup note: Homebrew `postgresql@18` was downloaded during setup but remains
  unlinked after an installation-path issue. Original `libpq` command links were restored.
  Tests used the cached `postgres:18` Docker image instead; no native server was started.

Basic repeatable checks:

```bash
uv run pytest tests/test_day5.py -q
node tests/day5_dashboard_smoke.cjs data/processed/day5/<run>/dashboard.html
```

Database cases skip unless `SPARKCITY_DAY5_TEST_DSN` names the explicitly isolated test
database (localhost port 55439, database `sparkcity_day5_test`) or the designated temporary
Unix socket. The fixture refuses an existing analytics schema and drops only the schema it
creates. Set `SPARKCITY_DAY5_TEST_SNAPSHOT` to a completed local Day 5 directory to include
the full-data acceptance test. Never point this test fixture at S2.
