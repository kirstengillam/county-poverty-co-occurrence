# County Poverty Co-Occurrence Dashboard

🚧 **Work in progress.** SAIPE (poverty rate + median household income), LAUS (unemployment rate), and county boundaries are live end-to-end, from fetch through Postgres/GeoJSON, and the pipeline is instrumented with OpenTelemetry. A first Grafana Geomap layer (poverty rate) is built. Still to build: additional Geomap layers and the remaining datasets (Eviction Lab, Food Access, Vulcan CO2). See [project.md](project.md) for the full brief, dataset list, and build sequence — the steps below reflect what's actually implemented today.

## Layout

- `src/cpco/etl/` — one fetcher per data source (SAIPE, LAUS, Eviction Lab, Food Access Atlas, Vulcan CO2, TIGER/Line boundaries). SAIPE, LAUS, and boundaries are implemented; Eviction Lab, Food Access, and Vulcan CO2 are still stubs.
- `src/cpco/db/` — Postgres connection, schema (`county_metrics`, keyed by FIPS), and load/upsert helpers
- `src/cpco/telemetry/` — OpenTelemetry tracer setup, exported to Grafana Cloud
- `scripts/` — runnable entrypoints tying ETL + DB load together, one per dataset
- `data/raw/`, `data/interim/`, `data/processed/` — ETL working directories (gitignored)
- `boundaries/` — final county-boundaries GeoJSON served to Grafana Geomap
- `grafana/dashboards/` — exported JSON snapshot of the live Grafana Cloud dashboard, kept as a version-controlled reference (Grafana Cloud is managed, so this isn't auto-provisioned — re-export manually after UI changes; see `grafana/dashboards/README.md`)
- `grafana/provisioning/` — reserved for future dashboard-as-code automation (e.g. Terraform), currently unused

## Setup

Requires Python 3.11+ and a running Postgres instance.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Then fill in `.env`:

- `DATABASE_URL` — defaults to `postgresql://localhost:5432/cpco`; point it at your Postgres instance. This project uses [Neon](https://neon.tech)'s free tier — its connection string includes `?sslmode=require`, which SQLAlchemy/psycopg2 handle natively.
- `TARGET_STATE_FIPS` — 2-digit state FIPS code for the state/region in scope (e.g. `06` for California)
- `CENSUS_API_KEY` — required by the SAIPE fetch; register at [api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html) and activate via the confirmation email before use
- `BLS_API_KEY` — required by the LAUS fetch; register at [data.bls.gov/registrationEngine](https://data.bls.gov/registrationEngine/) (registered keys allow up to 50 series per request, vs. 25 unregistered — needed since a state's counties can exceed that)

- `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` — optional; point these at your Grafana Cloud OTLP endpoint to export traces there. Left blank, spans print to the console instead, which is enough to confirm instrumentation is working locally.

## Tests

```bash
pytest
```

Tests run against an in-memory SQLite engine, so they don't need Postgres.

## Running the pipeline

So far, only the SAIPE (poverty rate + median household income) step is wired up end-to-end: fetch from the Census API, then upsert into Postgres keyed by `(fips, metric, year)`.

```bash
python scripts/run_saipe.py
```

This creates the `county_metrics` table if it doesn't exist and loads one row per county per metric for `TARGET_STATE_FIPS`. Safe to rerun — it upserts rather than duplicating rows. It prints a `Loaded N rows for state ...` line on success (confirmed against Neon: 116 rows for CA — 58 counties x 2 metrics).

To independently verify what landed in the table:

```bash
python -c "
from cpco.db.connection import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    print(conn.execute(text('SELECT COUNT(*) FROM county_metrics')).scalar())
"
```

County boundaries (TIGER/Line, converted to GeoJSON for Grafana Geomap) are also wired up:

```bash
python scripts/run_boundaries.py
```

This downloads the national TIGER/Line county file (~80MB, cached in `data/raw/` after the first run), filters to `TARGET_STATE_FIPS`, and writes `boundaries/county-boundaries.geojson`. Run this before `run_laus.py` — it's what populates the `counties` table that `run_laus.py` reads the county FIPS list from.

LAUS (unemployment rate) is also wired up:

```bash
python scripts/run_laus.py
```

This queries the BLS API for the annual-average unemployment rate for every county in the `counties` table (built via one BLS series ID per county, batched to stay under the API's 50-series-per-request limit) and upserts into `county_metrics`.
