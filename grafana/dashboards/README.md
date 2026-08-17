# Dashboard exports

This directory holds a version-controlled copy of the live dashboard, exported from Grafana Cloud. It's a backup/reference, not something Grafana reads — Grafana Cloud is a managed instance, so file-based provisioning (mounting this folder into Grafana's config) isn't possible here. To make this live-provisioned instead, it'd need a push mechanism such as Terraform (`grafana` provider) or the Grafana HTTP API.

## Updating

After changing the dashboard in the Grafana Cloud UI:

1. Share icon → **Export** tab → toggle "Export for sharing externally" **off** → **Save to file**.
2. Overwrite `county-poverty-geomap.json` with the downloaded file.
3. Commit.

The exported filename from Grafana includes a random ID (e.g. `County Poverty-1786992286674.json`) — rename it back to `county-poverty-geomap.json` when you overwrite.

## Adding a new Geomap layer for another metric

The current dashboard has one panel, "Poverty Rate by County," with a GeoJSON layer styled by manual threshold rules against `poverty_rate` (the standard, stable GeoJSON layer — not the alpha Dynamic GeoJSON layer; see `project.md`'s Known Issues section for why). Every metric baked into `boundaries/county-boundaries.geojson` (currently `poverty_rate`, `median_household_income`, `unemployment_rate`) is available as a feature property to style by the same way.

Since this project's goal is a **co-occurrence view** — seeing where conditions cluster, not toggling between them one at a time — duplicating the panel so each metric gets its own map, viewed side by side, fits better than stacking multiple fill layers on one map (which would just occlude each other).

To add an unemployment-rate panel:

1. Open the dashboard, hover the "Poverty Rate by County" panel, press `e` (or panel menu → **Edit**).
2. Panel menu → **More** → **Duplicate**. This copies the query and the GeoJSON layer config.
3. On the duplicate, rename the panel title to "Unemployment Rate by County (CA, 2022)".
4. In the panel's query editor, no query change is needed if you're using the GeoJSON's own baked properties — but if the panel still points its threshold rules at a Postgres query column instead, update the SQL to pull `unemployment_rate` instead of `poverty_rate` (`SELECT c.name, c.lat, c.lon, m.value AS unemployment_rate FROM counties c JOIN county_metrics m ON m.fips = c.fips WHERE m.metric = 'unemployment_rate' AND m.year = 2022`).
5. In the layer's style rules (Layer settings → Data style rules), change the property each rule checks from `poverty_rate` to `unemployment_rate`, and rescale the thresholds — the two metrics have very different ranges. CA 2022 unemployment rate runs 2.6%–15.3% (mean ~5.1%), vs. poverty rate's ~10–20%+ tiers, so something like:
   - `>= 10` → red (high)
   - `>= 7` → orange (elevated)
   - `>= 4` → yellow (moderate)
   - below 4 → default/green (low)
6. Drag the new panel into position (e.g. beside the poverty panel, so both render on the same screen for visual co-occurrence comparison).
7. Save the dashboard, then re-export following the steps above so `county-poverty-geomap.json` in this repo stays current.

The same recipe applies to future metrics (Eviction Lab, Food Access, Vulcan CO2) once they're landed in Postgres and re-baked into the GeoJSON via `python scripts/run_boundaries.py`.
