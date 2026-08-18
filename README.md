# County Poverty Co-Occurrence Dashboard

🚧 **Work in progress.** SAIPE (poverty rate + median household income), LAUS (unemployment rate), Eviction Lab (eviction filing rate), Food Access Atlas (food desert population share), and county boundaries are live end-to-end, from fetch through Postgres/GeoJSON, and the pipeline is instrumented with OpenTelemetry. Three Grafana Geomap layers (poverty rate, unemployment rate, eviction filing rate) are built. Still to build: a food-desert Geomap layer and Vulcan CO2 — the last remaining dataset, needing raster→county zonal statistics. See [project.md](project.md) for the full brief, dataset list, and build sequence — the steps below reflect what's actually implemented today.

## Layout

- `src/cpco/etl/` — one fetcher per data source (SAIPE, LAUS, Eviction Lab, Food Access Atlas, Vulcan CO2, TIGER/Line boundaries). SAIPE, LAUS, Eviction Lab, Food Access Atlas, and boundaries are implemented; Vulcan CO2 is still a stub.
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

No env var is needed for Eviction Lab. The county-level file it needs lives in the `eviction-lab-data-downloads` S3 bucket ([browsable at data-downloads.evictionlab.org](https://data-downloads.evictionlab.org/)), which is public and ODC-BY 1.0 licensed — `eviction_lab.py` fetches it directly over plain HTTPS, no key or auth required. (The email-gated form at [evictionlab.org/get-the-data](https://evictionlab.org/get-the-data/) is a separate, older marketing page for the same lab that happens to link to this bucket — it's how this file was discovered, but it's not in the actual fetch path.)

No env var is needed for Food Access Atlas either — USDA's [download page](https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/) links directly to a public ZIP, no gate at all.

- `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` — optional; point these at your Grafana Cloud OTLP endpoint to export traces there. Left blank, spans print to the console instead, which is enough to confirm instrumentation is working locally.

## Tests

```bash
pytest
```

Tests run against an in-memory SQLite engine, so they don't need Postgres.

## Running the pipeline

Four datasets are wired up end-to-end so far: SAIPE (poverty rate + median household income), LAUS (unemployment rate), Eviction Lab (eviction filing rate), and Food Access Atlas (food desert population share). Each lands in Postgres keyed by `(fips, metric, year)`. Boundaries (TIGER/Line, converted to GeoJSON for Grafana Geomap) ties them together — it populates the `counties` table other scripts depend on, and bakes the latest loaded value of every metric into the GeoJSON Grafana reads.

**Run order matters.** `run_boundaries.py` needs to run once before `run_laus.py` (to populate `counties`), and again after any metrics script to refresh the baked GeoJSON with the latest values — Grafana reads the static file, not Postgres directly, so nothing shows up on the dashboard until you re-bake:

```bash
python scripts/run_boundaries.py     # 1. bootstrap counties table + plain GeoJSON
python scripts/run_saipe.py          # 2. load poverty_rate, median_household_income
python scripts/run_laus.py           # 3. load unemployment_rate (needs counties table from step 1)
python scripts/run_eviction_lab.py   # 4. load eviction_filing_rate
python scripts/run_food_access.py    # 5. load food_desert_population_share
python scripts/run_boundaries.py     # 6. re-run to bake all current metric values into the GeoJSON
```

- `run_saipe.py` — creates the `county_metrics` table if it doesn't exist and loads one row per county per metric for `TARGET_STATE_FIPS`. Prints `Loaded N rows for state ...` on success (confirmed against Neon: 116 rows for CA — 58 counties x 2 metrics, year 2022).
- `run_laus.py` — queries the BLS API for the annual-average unemployment rate for every county in the `counties` table (one BLS series ID per county, batched to stay under the API's 50-series-per-request limit) and upserts into `county_metrics`. Confirmed against Neon: 58 rows for CA, year 2022.
- `run_eviction_lab.py` — reads eviction filing counts and renting-household counts from Eviction Lab's [public data downloads](https://data-downloads.evictionlab.org/) (cached in `data/raw/` after the first run, like the TIGER file), computes filing rate (`filings / renting households × 100`) per county, and upserts. Defaults to **2017**, not 2022 — Eviction Lab's source file only covers 2000-2018, and 2017 is the most recent year with data for every CA county. Confirmed against Neon: 58 rows for CA.
- `run_food_access.py` — reads USDA's tract-level [Food Access Research Atlas](https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/) (cached in `data/raw/`), then rolls it up to county via `food_access.aggregate_to_county`: for each county, `Σ(tract population × is-food-desert flag) / Σ(tract population) × 100`. No spatial join needed — a census tract's 11-digit GEOID already starts with its 5-digit county FIPS, so the rollup is a plain population-weighted groupby. This is the pipeline's first genuine "aggregation" dataset per `project.md`'s build sequence (step 3), unlike the three county-direct datasets before it. Year is fixed at **2019** (the source's own vintage: 2019 supermarket list, 2010 Census population, 2014–18 ACS). Confirmed against Neon: 58 rows for CA, aggregated from 8,024 tracts.
- `run_boundaries.py` — downloads the national TIGER/Line county file (~80MB, cached in `data/raw/` after the first run), filters to `TARGET_STATE_FIPS`, upserts county centroids into the `counties` table, and writes both `boundaries/county-boundaries-plain.geojson` (no metric values) and `boundaries/county-boundaries.geojson` (baked-in feature properties). Each metric is baked using **its own latest loaded year** (`db.load.fetch_metrics_wide_latest`) rather than one fixed year — necessary once datasets land at different years (2022 for SAIPE/LAUS, 2017 for Eviction Lab, 2019 for Food Access); a single fixed year would silently drop any metric not loaded for that year.

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

SAIPE, LAUS, and Eviction Lab are all county-direct (no aggregation needed) and follow the same shape. Food Access Atlas needed one extra step — tract→county aggregation — but turned out not to need geopandas or a spatial join, since a census tract's GEOID already encodes its county FIPS as a prefix; the rollup is a plain population-weighted `groupby`. Vulcan CO2, the last remaining stub, is a genuinely different shape: a 1km gridded raster with no FIPS embedded anywhere, so it'll need an actual spatial zonal-statistics step (`geopandas` + `rasterstats`, per `project.md`'s Architecture section) against the county boundary polygons.

The general pattern, adapted to whichever of these shapes fits:

1. Implement `fetch(...)` in `src/cpco/etl/<dataset>.py` (see `saipe.py` for a live API fetch, `eviction_lab.py` for a cached-static-file fetch, or `food_access.py` for a cached file needing tract-level pre-aggregation). If aggregation is needed, keep `fetch` returning raw source-level rows and add a separate `aggregate_to_county(...)` step (see `food_access.py`) — don't conflate the two.
2. The aggregation (or fetch, if none is needed) should ultimately produce a `DataFrame` with columns `fips, metric, year, value, source`.
3. Write `tests/test_<dataset>.py` mocking the HTTP call and, if there's an aggregation step, testing it separately with a small hand-built frame (see `tests/test_food_access.py`).
4. Add `scripts/run_<dataset>.py` that calls `init_schema`, `fetch(...)` (+ `aggregate_to_county(...)` if applicable), then `upsert_metrics(df, engine)` — copy `run_food_access.py` or `run_eviction_lab.py` as a starting point.
5. Add any new required env var (API key, etc.) to `.env.example` and this README's Setup section.
6. Re-run `python scripts/run_boundaries.py` afterward to bake the new metric into the GeoJSON — no need to worry about which year the new dataset lands at, `fetch_metrics_wide_latest` picks each metric's own latest year automatically.
