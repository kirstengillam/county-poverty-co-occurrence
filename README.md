# County Poverty Co-Occurrence Dashboard

✅ **Feature-complete per `project.md`'s build sequence.** All five datasets — SAIPE (poverty rate + median household income), LAUS (unemployment rate), Eviction Lab (eviction filing rate), Food Access Atlas (food desert population share), and Vulcan CO2 (total emissions) — plus county boundaries are live end-to-end, from fetch through Postgres/GeoJSON, and the pipeline is instrumented with OpenTelemetry. All five have a Grafana Geomap panel. See [project.md](project.md) for the full brief, dataset list, and any open items in its Known Issues section — the steps below reflect what's actually implemented today.

## Layout

- `src/cpco/etl/` — one fetcher per data source (SAIPE, LAUS, Eviction Lab, Food Access Atlas, Vulcan CO2, TIGER/Line boundaries). All are implemented.
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

No env var is needed for Vulcan CO2 — its [Zenodo record](https://zenodo.org/records/15446748) is a public download, no key or auth required. **Its license needs care, though:** the raw 1km raster is CC BY-NC-**ND** 4.0 (No Derivatives), not CC BY-NC as `project.md` originally assumed. The license text (Section 2(a)) permits reproducing/sharing the Licensed Material "in whole or in part" *unmodified*, but only permits *producing*, not *sharing*, Adapted Material (anything transformed/aggregated). So `vulcan_co2.fetch()` uses Vulcan's own pre-aggregated county-level file, filtered to a state and numerically untouched — that's the part we publish. A from-scratch raster→county rollup (`vulcan_co2.compute_zonal_stats()`, run via `scripts/verify_vulcan_co2_zonal_stats.py`) exists too, purely as a local learning/sanity-check exercise per `project.md`'s original suggestion — its output is never committed, baked into the GeoJSON, or otherwise published.

- `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` — optional; point these at your Grafana Cloud OTLP endpoint to export traces there. Left blank, spans print to the console instead, which is enough to confirm instrumentation is working locally.

## Tests

```bash
pytest
```

Tests run against an in-memory SQLite engine, so they don't need Postgres.

## Running the pipeline

All five datasets are wired up end-to-end: SAIPE (poverty rate + median household income), LAUS (unemployment rate), Eviction Lab (eviction filing rate), Food Access Atlas (food desert population share), and Vulcan CO2 (total emissions). Each lands in Postgres keyed by `(fips, metric, year)`. Boundaries (TIGER/Line, converted to GeoJSON for Grafana Geomap) ties them together — it populates the `counties` table other scripts depend on, and bakes the latest loaded value of every metric into the GeoJSON Grafana reads.

**Run order matters.** `run_boundaries.py` needs to run once before `run_laus.py` (to populate `counties`), and again after any metrics script to refresh the baked GeoJSON with the latest values — Grafana reads the static file, not Postgres directly, so nothing shows up on the dashboard until you re-bake:

```bash
python scripts/run_boundaries.py     # 1. bootstrap counties table + plain GeoJSON
python scripts/run_saipe.py          # 2. load poverty_rate, median_household_income
python scripts/run_laus.py           # 3. load unemployment_rate (needs counties table from step 1)
python scripts/run_eviction_lab.py   # 4. load eviction_filing_rate
python scripts/run_food_access.py    # 5. load food_desert_population_share
python scripts/run_vulcan_co2.py     # 6. load co2_emissions_total_kt
python scripts/run_boundaries.py     # 7. re-run to bake all current metric values into the GeoJSON
```

- `run_saipe.py` — creates the `county_metrics` table if it doesn't exist and loads one row per county per metric for `TARGET_STATE_FIPS`. Prints `Loaded N rows for state ...` on success (confirmed against Neon: 116 rows for CA — 58 counties x 2 metrics, year 2022).
- `run_laus.py` — queries the BLS API for the annual-average unemployment rate for every county in the `counties` table (one BLS series ID per county, batched to stay under the API's 50-series-per-request limit) and upserts into `county_metrics`. Confirmed against Neon: 58 rows for CA, year 2022.
- `run_eviction_lab.py` — reads eviction filing counts and renting-household counts from Eviction Lab's [public data downloads](https://data-downloads.evictionlab.org/) (cached in `data/raw/` after the first run, like the TIGER file), computes filing rate (`filings / renting households × 100`) per county, and upserts. Defaults to **2017**, not 2022 — Eviction Lab's source file only covers 2000-2018, and 2017 is the most recent year with data for every CA county. Confirmed against Neon: 58 rows for CA.
- `run_food_access.py` — reads USDA's tract-level [Food Access Research Atlas](https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/) (cached in `data/raw/`), then rolls it up to county via `food_access.aggregate_to_county`: for each county, `Σ(tract population × is-food-desert flag) / Σ(tract population) × 100`. No spatial join needed — a census tract's 11-digit GEOID already starts with its 5-digit county FIPS, so the rollup is a plain population-weighted groupby. This is the pipeline's first genuine "aggregation" dataset per `project.md`'s build sequence (step 3), unlike the three county-direct datasets before it. Year is fixed at **2019** (the source's own vintage: 2019 supermarket list, 2010 Census population, 2014–18 ACS). Confirmed against Neon: 58 rows for CA, aggregated from 8,024 tracts.
- `run_vulcan_co2.py` — reads Vulcan's own pre-aggregated county-level CO2 file (cached in `data/raw/`; see the Setup section above on why this project uses that file rather than computing its own raster rollup for the published metric), converts tons-of-carbon to tons-of-CO2 (×44/12, the molecular weight ratio — the source reports carbon mass, not CO2 mass), and upserts as `co2_emissions_total_kt`. **This metric is a total, not a rate** like the other four — larger, more industrial counties will simply read higher regardless of population, so read it as "where do emissions concentrate," not "emissions per resident." Year fixed at **2022**. Confirmed against Neon: 58 rows for CA.
- `run_boundaries.py` — downloads the national TIGER/Line county file (~80MB, cached in `data/raw/` after the first run), filters to `TARGET_STATE_FIPS`, upserts county centroids into the `counties` table, and writes both `boundaries/county-boundaries-plain.geojson` (no metric values) and `boundaries/county-boundaries.geojson` (baked-in feature properties). Each metric is baked using **its own latest loaded year** (`db.load.fetch_metrics_wide_latest`) rather than one fixed year — necessary once datasets land at different years (2022 for SAIPE/LAUS/Vulcan, 2017 for Eviction Lab, 2019 for Food Access); a single fixed year would silently drop any metric not loaded for that year.

```bash
python scripts/verify_vulcan_co2_zonal_stats.py
```

This one is separate from the pipeline above — it downloads the raw 1km raster (~400MB, cached in `data/raw/`) and computes county totals directly via `geopandas` + `rasterstats` zonal statistics, then prints a comparison against the official file `run_vulcan_co2.py` actually loads. It's a one-off learning/sanity-check exercise (per `project.md`'s original suggestion), not something to run as part of the regular pipeline — its output is never persisted anywhere. Last run: mean absolute difference of 1.51% across all 58 CA counties, confirming both the official file and the from-scratch raster rollup agree.

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

All five datasets in this pipeline are implemented, but the pattern generalizes for adding a sixth. SAIPE, LAUS, and Eviction Lab are all county-direct (no aggregation needed). Food Access Atlas needed one extra step — tract→county aggregation — but turned out not to need geopandas or a spatial join, since a census tract's GEOID already encodes its county FIPS as a prefix; the rollup is a plain population-weighted `groupby`. Vulcan CO2 needed a genuinely different shape: a 1km gridded raster with no FIPS embedded anywhere, requiring an actual spatial zonal-statistics step (`geopandas` + `rasterstats` against the county boundary polygons) — and its license (CC BY-NC-ND) meant the self-computed rollup could only be used locally, not published; see the Setup section above.

The general pattern, adapted to whichever of these shapes fits:

1. Implement `fetch(...)` in `src/cpco/etl/<dataset>.py` (see `saipe.py` for a live API fetch, `eviction_lab.py` for a cached-static-file fetch, `food_access.py` for a cached file needing tract-level pre-aggregation, or `vulcan_co2.py` for a source needing raster zonal statistics — and a worked example of using a pre-aggregated official file to sidestep a No-Derivatives license). If aggregation is needed, keep `fetch` returning raw source-level rows and add a separate `aggregate_to_county(...)` step (see `food_access.py`) — don't conflate the two.
2. The aggregation (or fetch, if none is needed) should ultimately produce a `DataFrame` with columns `fips, metric, year, value, source`.
3. Write `tests/test_<dataset>.py` mocking the HTTP call and, if there's an aggregation step, testing it separately with a small hand-built frame (see `tests/test_food_access.py`).
4. Add `scripts/run_<dataset>.py` that calls `init_schema`, `fetch(...)` (+ `aggregate_to_county(...)` if applicable), then `upsert_metrics(df, engine)` — copy `run_food_access.py` or `run_eviction_lab.py` as a starting point.
5. Add any new required env var (API key, etc.) to `.env.example` and this README's Setup section.
6. Re-run `python scripts/run_boundaries.py` afterward to bake the new metric into the GeoJSON — no need to worry about which year the new dataset lands at, `fetch_metrics_wide_latest` picks each metric's own latest year automatically.
