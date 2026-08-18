# Project Brief: County-Level Poverty Co-Occurrence Dashboard

## Purpose

A standalone portfolio project to build hands-on experience with three things not yet reflected in my resume: **geospatial data processing**, **OpenTelemetry instrumentation**, and **Grafana dashboards** (specifically the Geomap panel). Secondary goal: a project that fits naturally alongside my target roles in climate/civic tech/social impact.

Go is explicitly out of scope for this project — the geospatial libraries needed (raster zonal statistics, tract-to-county aggregation) are far more mature in Python, so the ETL layer will be Python. Go exposure will come from a separate, smaller project later.

## Concept

An interactive county-level map that overlays several public datasets often discussed together in the context of economic hardship: poverty rate, food access, eviction rates, unemployment, and CO2 emissions. The goal is a **co-occurrence view** — where do these conditions cluster geographically — not a causal claim about "effects of poverty." 

## Scope Guardrails

- Start with **one state or metro region**, not the full country. Widen later if the pipeline holds up.
- Get **one layer working end-to-end** (recommend poverty rate, since it's the backbone dataset and needs no aggregation) before adding the others.
- Treat the two datasets that need aggregation (Food Access Research Atlas, Vulcan CO2) as the hardest part of the project and budget time accordingly.
- **County is the baseline granularity for v1.** Finer-grained display (e.g. showing Food Access at its native census-tract resolution instead of rolling it up) is desired as a **second pass**, once the county-level pipeline is working end-to-end — not before. Would require a `geo_level` column on the metrics table, a second (tract) boundaries GeoJSON, and a second Grafana Geomap layer per applicable dataset.

## Datasets

| Dataset | Source | Granularity | Notes |
|---|---|---|---|
| **Poverty rate & median household income** (backbone layer) | [Census SAIPE](https://www.census.gov/programs-surveys/saipe.html) — [county/state download page](https://www.census.gov/programs-surveys/saipe/data/datasets.html) | County (direct) | Annual, model-based estimates; only federal source for current-year county median household income. No aggregation needed — join directly on FIPS. |
| **Unemployment rate** | [BLS Local Area Unemployment Statistics (LAUS)](https://www.bls.gov/lau/) | County (direct) | Monthly and annual county-level series. No aggregation needed. |
| **Eviction filings/rates** | [Eviction Lab, Princeton University](https://evictionlab.org/) | County (direct) | University-hosted, stable. No aggregation needed. |
| **Food access ("food desert") indicators** | [USDA Food Access Research Atlas](https://www.ers.usda.gov/data-products/food-access-research-atlas) | Census tract | Needs population-weighted aggregation up to county before it can join the rest. |
| **CO2 emissions (fossil fuel combustion)** | [Vulcan Project v4.0, NASA/Northern Arizona University](https://zenodo.org/records/15446748) ([methodology paper](https://www.nature.com/articles/s41597-025-06391-w)) | 1km gridded raster, annual, 2010–2022 | Needs zonal statistics (sum emissions within each county polygon) to roll up to county level. Zenodo also has pre-aggregated county-level `.xlsx` files — used as the actual publishable metric; see Known Issues below on why. **Licensed CC BY-NC-ND 4.0** (No Derivatives — corrected 2026-08-18; the license badge on the Zenodo page is misleadingly labeled "CC BY-NC 4.0 DEED" but the badge icon and the legal-text link it points to are both `by-nc-nd`). Non-commercial fits a portfolio project, but "No Derivatives" means a self-computed zonal-stats rollup can't be published. |
| **County boundaries** | [Census TIGER/Line Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | County polygons | Convert to GeoJSON; this is what Grafana's Geomap panel renders and joins to metrics by FIPS. Not stored in Postgres — served as a static file. |

**Data stability note:** Federal health/climate/environmental datasets have been inconsistently available since early 2025 (CDC alone removed ~13% of its public datasets in a short window). The datasets above were chosen partly for this reason — Eviction Lab (university), Vulcan (NASA/university, hosted on Zenodo), and SAIPE/LAUS/TIGER (Census/BLS, core statistical products less likely to be affected) are comparatively stable, but it's worth a quick liveness check on each before committing.

## Architecture

- **Join key:** 5-digit county FIPS code, used across every dataset.
- **ETL / aggregation (Python):** `geopandas` + `rasterstats` for the Vulcan raster-to-county zonal statistics; `geopandas` + `pandas` for the tract-to-county population-weighted aggregation on the Food Access Research Atlas. Straightforward fetch/parse for SAIPE, LAUS, and Eviction Lab (already county-level).
- **Storage:** Postgres, one row per county per metric (or a wide table keyed by FIPS). PostGIS isn't required — boundary geometry lives in a static GeoJSON file, not the database, since Grafana Geomap does the spatial join at render time.
- **Observability:** OpenTelemetry SDK instrumenting the pipeline, with each data-source fetch, the tract-to-county aggregation step, and the raster zonal-stats step as distinct spans. Export via OTLP to Grafana Cloud's free tier (avoids self-hosting a collector).
- **Visualization:** Grafana Geomap panel, one layer per metric, toggleable. Boundaries from the TIGER/Line-derived GeoJSON, values from the Postgres FIPS-keyed table.

## Build Sequence

1. Scope to one state or metro region.
2. Confirm FIPS as the join key across all five datasets.
3. Build the aggregation step for the two mismatched-granularity datasets (Food Access Atlas tract→county; Vulcan raster→county zonal stats). This is the highest-effort, highest-learning step.
4. Land all metrics in Postgres, keyed by FIPS.
5. Pull and convert TIGER/Line county boundaries to GeoJSON.
6. Instrument the pipeline with OpenTelemetry, exporting to Grafana Cloud.
7. Build the Grafana Geomap dashboard, starting with a single layer (poverty rate) before adding the rest.

## Known Issues / Revisit Later

**Grafana Geomap's "Dynamic GeoJSON (Alpha)" layer — abandoned for now, 2026-08-13.** This layer type would have given a true choropleth (county polygons filled/colored live from a SQL query, joined on `fips`) without needing to bake values into the GeoJSON file. It's gated behind a server-side `enable_alpha` flag not exposed to Grafana Cloud users by default — had to email Grafana support to get it turned on for this stack.

Once enabled, configured it fully per the docs: GeoJSON URL pointed at the raw GitHub URL for `boundaries/county-boundaries.geojson`, ID Field set to `fips` (matching the GeoJSON's `fips` property), Data style Color field bound to `poverty_rate`, and panel Standard options Color scheme set to a "by value" gradient (Yellow-Red). Independently verified via Query Inspector that the underlying query was returning correctly-typed, zero-padded `fips` strings (e.g. `"06001"`) and `poverty_rate` values. Despite every setting being correct, the layer consistently rendered every county in the flat "Default style" color instead of the data-driven gradient — meaning the query-to-GeoJSON join wasn't actually happening at render time. This matches several Grafana community forum threads describing this specific layer as underdocumented and inconsistent in alpha.

**Fallback adopted instead:** bake the current metric value directly into `county-boundaries.geojson` as a static property (regenerated whenever the underlying data changes), and use the standard, stable (non-alpha) GeoJSON layer with manual style rules based on value thresholds. Less elegant — no live gradient, no automatic update when Postgres data changes — but reliable.

**Worth revisiting:** if/when Dynamic GeoJSON graduates out of alpha (or gets better documented), it's the better long-term approach — swap back to a live query-driven choropleth instead of regenerating a static file.

**Vulcan CO2 license correction — 2026-08-18.** This brief originally described the Vulcan data as CC BY-NC 4.0. The actual license on the live Zenodo record is **CC BY-NC-ND 4.0** — the Zenodo UI badge is misleadingly labeled "CC BY-NC 4.0 DEED," but the badge icon and its legal-text link both resolve to `by-nc-nd`. "No Derivatives" matters here specifically because the planned zonal-stats rollup *is* a derivative.

Read the actual license text (Section 2(a)) rather than just the summary: it separately grants the right to "reproduce and Share... in whole or in part" the Licensed Material *unmodified*, versus the right to only "produce and reproduce, but not Share" Adapted Material. That distinction is load-bearing:

- Computing county totals ourselves from the raw raster (`vulcan_co2.compute_zonal_stats`) produces Adapted Material — legally fine to run and use locally, not fine to publish.
- Using Vulcan's own pre-aggregated county-level file (`v4.all.co2.county.mn.allyrs.xlsx`), filtered to CA and numerically untouched, is "Share... in part" of the unmodified Licensed Material — this is what actually lands in Postgres/GeoJSON/the dashboard (`vulcan_co2.fetch`).

Net effect: the pipeline still does the real raster zonal-statistics work (`scripts/verify_vulcan_co2_zonal_stats.py`, run locally, gitignored raw raster, no output ever committed) — that's the actual `geopandas`/`rasterstats` skill this dataset was chosen to exercise, and it cross-validated against the official file to within 1.51% mean absolute difference across all 58 CA counties. But the number that's public is Vulcan's own, not a self-computed derivative.

## Resume/Portfolio Framing (for later)

Once built, this should support an honest bullet along the lines of: *"Built a county-level geospatial dashboard combining five public datasets (poverty, unemployment, eviction, food access, and CO2 emissions), including raster-to-polygon aggregation via zonal statistics; instrumented the ETL pipeline with OpenTelemetry and visualized via Grafana Geomap."* Keep the framing to "co-occurrence" rather than "effects of poverty" in any write-up or interview description.