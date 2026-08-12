# County Poverty Co-Occurrence Dashboard

See [project.md](project.md) for the full project brief, dataset list, and build sequence.

## Layout

- `src/cpco/etl/` — one fetcher per data source (SAIPE, LAUS, Eviction Lab, Food Access Atlas, Vulcan CO2, TIGER/Line boundaries)
- `src/cpco/db/` — Postgres connection and schema (`county_metrics`, keyed by FIPS)
- `src/cpco/telemetry/` — OpenTelemetry tracer setup, exported to Grafana Cloud
- `data/raw/`, `data/interim/`, `data/processed/` — ETL working directories (gitignored)
- `boundaries/` — final county-boundaries GeoJSON served to Grafana Geomap
- `grafana/dashboards/`, `grafana/provisioning/` — Geomap dashboard definitions

## Setup

```bash
cp .env.example .env
pip install -e ".[dev]"
```
