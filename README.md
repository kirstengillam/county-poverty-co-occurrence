# County Poverty Co-Occurrence Dashboard

See [project.md](project.md) for the full project brief, dataset list, and build sequence.

## Layout

- `src/cpco/etl/` — one fetcher per data source (SAIPE, LAUS, Eviction Lab, Food Access Atlas, Vulcan CO2, TIGER/Line boundaries). SAIPE and boundaries are implemented; LAUS, Eviction Lab, Food Access, and Vulcan CO2 are still stubs.
- `src/cpco/db/` — Postgres connection, schema (`county_metrics`, keyed by FIPS), and load/upsert helpers
- `src/cpco/telemetry/` — OpenTelemetry tracer setup, exported to Grafana Cloud
- `scripts/` — runnable entrypoints tying ETL + DB load together, one per dataset
- `data/raw/`, `data/interim/`, `data/processed/` — ETL working directories (gitignored)
- `boundaries/` — final county-boundaries GeoJSON served to Grafana Geomap
- `grafana/dashboards/`, `grafana/provisioning/` — Geomap dashboard definitions

## Setup

Requires Python 3.11+ and a running Postgres instance.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Then fill in `.env`:

- `DATABASE_URL` — defaults to `postgresql://localhost:5432/cpco`; point it at your local Postgres
- `TARGET_STATE_FIPS` — 2-digit state FIPS code for the state/region in scope (e.g. `06` for California)
- `CENSUS_API_KEY` — required by the SAIPE fetch; register at [api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html) and activate via the confirmation email before use

`OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` aren't needed yet — those come in once the pipeline is instrumented.

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

This creates the `county_metrics` table if it doesn't exist and loads one row per county per metric for `TARGET_STATE_FIPS`. Safe to rerun — it upserts rather than duplicating rows.

County boundaries (TIGER/Line, converted to GeoJSON for Grafana Geomap) are also wired up:

```bash
python scripts/run_boundaries.py
```

This downloads the national TIGER/Line county file (~80MB, cached in `data/raw/` after the first run), filters to `TARGET_STATE_FIPS`, and writes `boundaries/county-boundaries.geojson`.
