# Dashboard exports

This directory holds a version-controlled copy of the live dashboard, exported from Grafana Cloud. It's a backup/reference, not something Grafana reads — Grafana Cloud is a managed instance, so file-based provisioning (mounting this folder into Grafana's config) isn't possible here. To make this live-provisioned instead, it'd need a push mechanism such as Terraform (`grafana` provider) or the Grafana HTTP API.

## Updating

**Preferred: edit the JSON directly, then import it.** Manual UI editing (duplicating a panel, retitling, updating its query and thresholds by hand) has caused three separate bugs across this project's panels so far — a leftover SQL query from the panel it was duplicated from (twice), and a threshold rule with a blank `property` field. Editing the checked-in JSON as code and pushing it back avoids that whole class of mistake.

1. Edit `county-poverty-geomap-california.json` directly.
2. In Grafana Cloud, open the dashboard → gear icon (Settings) → **JSON Model** → paste the updated JSON → **Save**. This updates the *existing* dashboard by its UID.
   - Don't use **Dashboards → New → Import** for this — that flow treats the file as a new upload and can create a duplicate dashboard instead of updating the live one.
3. Confirm the change rendered correctly in Grafana, then commit the file.

**Fallback: UI editing.** If a change is easier to explore visually first (e.g. testing threshold colors), edit in the Grafana UI as before, then Share icon → **Export** tab → toggle "Export for sharing externally" **off** → **Save to file**, overwrite `county-poverty-geomap-california.json` (Grafana's exported filename includes a random ID — rename it back), and double-check the query/property fields against what you intended before committing, given the track record above.

## Current state

Five panels, one per metric, all using the standard/stable GeoJSON layer with manual threshold-based style rules (not the alpha Dynamic GeoJSON layer — see `project.md`'s Known Issues section for why that was abandoned). Each is a separate panel rather than stacked layers on one map, since the project's goal is a **co-occurrence view** — seeing conditions side by side, not toggling between them.

| Panel | Metric property | Year | Thresholds (`>=` value → color) |
|---|---|---|---|
| Poverty Rate by County | `poverty_rate` | 2022 | 20 → red, 15 → orange, 10 → yellow |
| Unemployment Rate by County | `unemployment_rate` | 2022 | 10 → red, 7 → orange, 4 → yellow |
| Eviction Rate by County | `eviction_filing_rate` | 2017 | 3.5 → red, 2.5 → orange, 1.5 → yellow |
| Food Desert Population Share by County | `food_desert_population_share` | 2019 | 25 → red, 10 → orange, 2 → yellow |
| CO2 Emissions by County | `co2_emissions_total_kt` | 2022 | 4500 → red, 1900 → orange, 680 → yellow |

Below each threshold, panels fall through to the layer's default style (green). Thresholds were set from each metric's actual quartile distribution in the loaded CA data at the time, not off any universal scale — they don't carry over between metrics, and won't carry over to national scope either (see below). Re-check `MIN/MAX/AVG` (or quartiles) against fresh data before reusing them.

Eviction (2017) and Food Desert (2019) intentionally use different years than the other three (2022) — both sources' data simply doesn't extend that far; see `README.md`'s Running the pipeline section. CO2 Emissions is also the only **total**, not a rate — it reads as "where emissions concentrate," not "emissions per resident," since it isn't normalized by population.

The map view (`view.lat`/`view.lon`/`view.zoom` in each panel's `vizConfig`) is currently a California-scale camera position (`lat: 37.4, lon: -118.5, zoom: 4.87`). The panels' SQL queries and the GeoJSON `src` URL have no state filter at all — they render whatever's in `counties`/`county_metrics` and `boundaries/county-boundaries.geojson` respectively — so nothing about the queries needs to change if the pipeline is ever run for more than one state. The view/titles/thresholds do, though; see `project.md`'s Scope Guardrails on widening beyond one state.

## Adding a new Geomap layer for another metric

Every metric baked into `boundaries/county-boundaries.geojson` is available as a feature property to style by. To add a new panel, prefer editing the JSON directly (see Updating above) over UI duplication:

1. Copy an existing panel's block in `spec.elements` (e.g. `panel-5`), give it a new key (e.g. `panel-6`) and a new `spec.id`.
2. Retitle it to `<Metric Name> by County (<scope>, <year>)`.
3. Update its SQL query: `SELECT c.name, c.lat, c.lon, m.value AS <metric> FROM counties c JOIN county_metrics m ON m.fips = c.fips WHERE m.metric = '<metric>' AND m.year = <year>`. The map's fill color doesn't actually depend on this query (it reads the GeoJSON's baked properties directly), but the tooltip/data table does, so a stale query silently shows the wrong values on hover.
4. Update the layer's `rules` — change every rule's `check.property` to the new metric, and rescale `check.value` thresholds to that metric's own range. Pull real `MIN/MAX/AVG`/quartiles from Postgres first rather than guessing or reusing another metric's numbers (see the table above for the pattern).
5. Add a `GridLayoutItem` for the new panel in `spec.layout.spec.items`, positioned alongside the others so they render together for visual co-occurrence comparison.
6. Import via JSON Model (see Updating above), confirm it rendered correctly, then commit.

All five datasets from `project.md` now have a panel; this recipe is for whenever a sixth dataset gets added to the pipeline (see `README.md`'s "Adding a new dataset" section).
