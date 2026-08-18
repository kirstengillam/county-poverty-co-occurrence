# Dashboard exports

This directory holds a version-controlled copy of the live dashboard, exported from Grafana Cloud. It's a backup/reference, not something Grafana reads — Grafana Cloud is a managed instance, so file-based provisioning (mounting this folder into Grafana's config) isn't possible here. To make this live-provisioned instead, it'd need a push mechanism such as Terraform (`grafana` provider) or the Grafana HTTP API.

## Updating

After changing the dashboard in the Grafana Cloud UI:

1. Share icon → **Export** tab → toggle "Export for sharing externally" **off** → **Save to file**.
2. Overwrite `county-poverty-geomap.json` with the downloaded file.
3. Commit.

The exported filename from Grafana includes a random ID (e.g. `County Poverty-1786992286674.json`) — rename it back to `county-poverty-geomap.json` when you overwrite.

## Current state

Five panels, one per metric, all using the standard/stable GeoJSON layer with manual threshold-based style rules (not the alpha Dynamic GeoJSON layer — see `project.md`'s Known Issues section for why that was abandoned). Each is a separate panel rather than stacked layers on one map, since the project's goal is a **co-occurrence view** — seeing conditions side by side, not toggling between them.

| Panel | Metric property | Year | Thresholds (`>=` value → color) |
|---|---|---|---|
| Poverty Rate by County | `poverty_rate` | 2022 | 20 → red, 15 → orange, 10 → yellow |
| Unemployment Rate by County | `unemployment_rate` | 2022 | 10 → red, 7 → orange, 4 → yellow |
| Eviction Rate by County | `eviction_filing_rate` | 2017 | 3.5 → red, 2.5 → orange, 1.5 → yellow |
| Food Desert Population Share by County | `food_desert_population_share` | 2019 | 25 → red, 10 → orange, 2 → yellow |
| CO2 Emissions by County | `co2_emissions_total_kt` | 2022 | 4500 → red, 1900 → orange, 680 → yellow |

Below each threshold, panels fall through to the layer's default style (green). Thresholds were set from each metric's actual quartile distribution in the loaded CA data at the time, not off any universal scale — they don't carry over between metrics or between states if `TARGET_STATE_FIPS` ever changes. Re-check `MIN/MAX/AVG` (or quartiles) against fresh data before reusing them.

Eviction (2017) and Food Desert (2019) intentionally use different years than the other three (2022) — both sources' data simply doesn't extend that far; see `README.md`'s Running the pipeline section. CO2 Emissions is also the only **total**, not a rate — it reads as "where emissions concentrate," not "emissions per resident," since it isn't normalized by population.

## Adding a new Geomap layer for another metric

Every metric baked into `boundaries/county-boundaries.geojson` is available as a feature property to style by. To add a new panel:

1. Open the dashboard, hover an existing panel, press `e` (or panel menu → **Edit**).
2. Panel menu → **More** → **Duplicate**. This copies the query and the GeoJSON layer config.
3. On the duplicate, rename the panel title to `<Metric Name> by County (CA, <year>)`.
4. **Update the SQL query** — this is the step most likely to get missed when duplicating: `SELECT c.name, c.lat, c.lon, m.value AS <metric> FROM counties c JOIN county_metrics m ON m.fips = c.fips WHERE m.metric = '<metric>' AND m.year = <year>`. The map's fill color doesn't actually depend on this query (it reads the GeoJSON's baked properties directly), but the tooltip/data table does, so a stale query silently shows the wrong values on hover.
5. In the layer's style rules (Layer settings → Data style rules), change the property each rule checks to the new metric, and rescale the thresholds to that metric's own range — pull real `MIN/MAX/AVG`/quartiles from Postgres first rather than guessing or reusing another metric's numbers (see the table above for the pattern).
6. Drag the new panel into position alongside the others so they render together for visual co-occurrence comparison.
7. Save the dashboard, then re-export following the steps above so `county-poverty-geomap.json` in this repo stays current.

All five datasets from `project.md` now have a panel; this recipe is for whenever a sixth dataset gets added to the pipeline (see `README.md`'s "Adding a new dataset" section).
