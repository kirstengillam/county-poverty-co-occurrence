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

Two datasets are wired up end-to-end so far: SAIPE (poverty rate + median household income) and LAUS (unemployment rate). Both fetch from their source API and upsert into Postgres keyed by `(fips, metric, year)`. Boundaries (TIGER/Line, converted to GeoJSON for Grafana Geomap) ties them together — it populates the `counties` table other scripts depend on, and bakes whatever's currently in `county_metrics` into the GeoJSON Grafana reads.

**Run order matters.** `run_boundaries.py` needs to run once before `run_laus.py` (to populate `counties`), and again after any metrics script to refresh the baked GeoJSON with the latest values — Grafana reads the static file, not Postgres directly, so nothing shows up on the dashboard until you re-bake:

```bash
python scripts/run_boundaries.py   # 1. bootstrap counties table + plain GeoJSON
python scripts/run_saipe.py        # 2. load poverty_rate, median_household_income
python scripts/run_laus.py         # 3. load unemployment_rate (needs counties table from step 1)
python scripts/run_boundaries.py   # 4. re-run to bake all current metric values into the GeoJSON
```

- `run_saipe.py` — creates the `county_metrics` table if it doesn't exist and loads one row per county per metric for `TARGET_STATE_FIPS`. Prints `Loaded N rows for state ...` on success (confirmed against Neon: 116 rows for CA — 58 counties x 2 metrics).
- `run_laus.py` — queries the BLS API for the annual-average unemployment rate for every county in the `counties` table (one BLS series ID per county, batched to stay under the API's 50-series-per-request limit) and upserts into `county_metrics`. Confirmed against Neon: 58 rows for CA.
- `run_boundaries.py` — downloads the national TIGER/Line county file (~80MB, cached in `data/raw/` after the first run), filters to `TARGET_STATE_FIPS`, upserts county centroids into the `counties` table, and writes both `boundaries/county-boundaries-plain.geojson` (no metric values) and `boundaries/county-boundaries.geojson` (current metric values baked in as feature properties).

All scripts are safe to rerun — they upsert rather than duplicate rows.

To independently verify what landed in the table:

```bash
python -c "
from cpco.db.connection import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    print(conn.execute(text('SELECT COUNT(*) FROM county_metrics')).scalar())
"
```

### Adding a new dataset

SAIPE and LAUS are both county-direct (no aggregation needed), so they're the template for the next easy dataset (Eviction Lab). Food Access Atlas and Vulcan CO2 need tract→county or raster→county aggregation first — see `project.md`'s Architecture section — but land in Postgres the same way once aggregated. The pattern:

1. Implement `fetch(...)` in `src/cpco/etl/<dataset>.py`, returning a `DataFrame` with columns `fips, metric, year, value, source` (see `saipe.py` or `laus.py`).
2. Write `tests/test_<dataset>.py` mocking the HTTP call, asserting the returned frame's shape and a couple of values (see `tests/test_laus.py`).
3. Add `scripts/run_<dataset>.py` that calls `init_schema`, the new `fetch(...)`, then `upsert_metrics(df, engine)` — copy `run_laus.py` as a starting point.
4. Add any new required env var (API key, etc.) to `.env.example` and this README's Setup section.
5. Re-run `python scripts/run_boundaries.py` afterward to bake the new metric into the GeoJSON.
