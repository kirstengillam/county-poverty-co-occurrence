# Dashboard exports

This directory holds version-controlled copies of Grafana Cloud dashboards. They're a backup/reference, not something Grafana reads — Grafana Cloud is a managed instance, so file-based provisioning (mounting this folder into Grafana's config) isn't possible here. To make this live-provisioned instead, it'd need a push mechanism such as Terraform (`grafana` provider) or the Grafana HTTP API.

Two dashboard files, both derived from the same panel/query structure but scoped differently:

| File | Scope | Status |
|---|---|---|
| `county-poverty-geomap-california.json` | California (58 counties) | Live in Grafana Cloud, `uid: 10674e15-2161-4ef8-82a9-e04bcf1a5b69` |
| `county-poverty-geomap-us.json` | All US counties (3,235) | Live in Grafana Cloud, `uid: 748fb2f0-7f5e-46be-b346-5c94b15a29c4` — this is the original dashboard from the very start of this project; the California file above is a later duplicate that got its own separate UID when split off |

## Updating an existing dashboard

**Preferred: edit the JSON directly, then import it.** Manual UI editing (duplicating a panel, retitling, updating its query and thresholds by hand) has caused three separate bugs across this project's panels so far — a leftover SQL query from the panel it was duplicated from (twice), and a threshold rule with a blank `property` field. Editing the checked-in JSON as code and pushing it back avoids that whole class of mistake.

1. Edit the relevant file directly.
2. In Grafana Cloud, open the dashboard → gear icon (Settings) → **JSON Model** → paste the updated JSON → **Save**. This updates the *existing* dashboard by its UID.
   - Don't use **Dashboards → New → Import** for this — that flow treats the file as a new upload and can create a duplicate dashboard instead of updating the live one.
3. Confirm the change rendered correctly in Grafana, then commit the file.

**Fallback: UI editing.** If a change is easier to explore visually first (e.g. testing threshold colors), edit in the Grafana UI as before, then Share icon → **Export** tab → toggle "Export for sharing externally" **off** → **Save to file**, overwrite the file (Grafana's exported filename includes a random ID — rename it back), and double-check the query/property fields against what you intended before committing, given the track record above.

## Creating a new dashboard from one of these files

This is how `county-poverty-geomap-us.json` was produced — copied from the California file, then edited (title, panel titles, map view, GeoJSON `src`) without touching the SQL queries or thresholds (see Current State). Its `metadata.name`/`metadata.uid` are deliberately blank so importing it can't collide with or overwrite the California dashboard, which owns the original UID.

To bring a file like this into Grafana for the first time: **Dashboards → New → Import → Upload JSON file**, or create a blank new dashboard and paste the content into its **Settings → JSON Model**. Either way, this is the one case where the Import flow (rather than JSON Model on an existing dashboard) is correct, since the goal here actually is a new dashboard, not an update to an existing one.

## Current state

Five panels, one per metric, all using the standard/stable GeoJSON layer with manual threshold-based style rules (not the alpha Dynamic GeoJSON layer — see `project.md`'s Known Issues section for why that was abandoned). Each is a separate panel rather than stacked layers on one map, since the project's goal is a **co-occurrence view** — seeing conditions side by side, not toggling between them.

**California file** (`county-poverty-geomap-california.json`):

| Panel | Metric property | Year | Thresholds (`>=` value → color) |
|---|---|---|---|
| Poverty Rate by County | `poverty_rate` | 2022 | 20 → red, 15 → orange, 10 → yellow |
| Unemployment Rate by County | `unemployment_rate` | 2022 | 10 → red, 7 → orange, 4 → yellow |
| Eviction Rate by County | `eviction_filing_rate` | 2017 | 3.5 → red, 2.5 → orange, 1.5 → yellow |
| Food Desert Population Share by County | `food_desert_population_share` | 2019 | 25 → red, 10 → orange, 2 → yellow |
| CO2 Emissions by County | `co2_emissions_total_kt` | 2022 | 4500 → red, 1900 → orange, 680 → yellow |

**US file** (`county-poverty-geomap-us.json`) — same panels, thresholds set from real national quartiles (`SELECT value FROM county_metrics WHERE metric = ...` across all loaded states), not California's:

| Panel | Metric property | Year | National coverage | Thresholds (`>=` value → color) |
|---|---|---|---|---|
| Poverty Rate by County | `poverty_rate` | 2022 | 3,143 / 3,235 counties | 18 → red, 14 → orange, 11 → yellow |
| Unemployment Rate by County | `unemployment_rate` | 2022 | 3,221 / 3,235 counties | 4.5 → red, 3.5 → orange, 2.5 → yellow |
| Eviction Rate by County | `eviction_filing_rate` | 2017 | 1,402 / 3,235 counties | 4.5 → red, 2.75 → orange, 1.5 → yellow |
| Food Desert Population Share by County | `food_desert_population_share` | 2019 | 3,133 / 3,235 counties | 30 → red, 13 → orange, 2 → yellow |
| CO2 Emissions by County | `co2_emissions_total_kt` | 2022 | 3,133 / 3,235 counties | 1250 → red, 400 → orange, 165 → yellow |

Below the lowest threshold, panels fall through to the layer's default style (green). Counties with **no data at all** (no row in `county_metrics` for that metric — not the same as a real value of `0`) get a dedicated rule instead: `{operation: "eq", property: "<metric>", value: null}`, styled at `opacity: 0` (fully transparent), so gaps read as "nothing here" rather than blending into the lowest real-data color. This rule is listed first in each layer's `rules` array, ahead of the threshold checks.

This works because of how Grafana's rule engine (`compareValues.ts`) actually treats `null`: a missing GeoJSON property is normalized to a special null marker before comparing, and `null` only equals `null` — it is never `>=`/`<=`/`==` a real number, including `0`. So a real `0` (e.g. `food_desert_population_share = 0` for a dense urban county with no low-access tracts, or a genuine `0%` eviction filing rate for a small county) correctly still matches the normal threshold rules and renders with its real color; only a truly absent value matches the null rule. Confirmed against Grafana's own source rather than assumed, given this file's history of silent JSON bugs — see [`checkFeatureMatchesStyleRule.ts`](https://github.com/grafana/grafana/blob/main/public/app/plugins/panel/geomap/utils/checkFeatureMatchesStyleRule.ts) and [`compareValues.ts`](https://github.com/grafana/grafana/blob/main/packages/grafana-data/src/transformations/matchers/compareValues.ts).

Eviction's national coverage (43%) is much sparser than the rest — expected, see `eviction_lab.fetch`'s docstring: many jurisdictions never had court eviction records collected, not just missing recent years. That's exactly the kind of gap the null rule now makes visible on the map instead of silently coloring those counties as if they had a low (but real) eviction rate.

Thresholds were set from each metric's own quartile distribution in whichever data was loaded at the time (CA-only for the California file, national for the US file) — they don't carry over between metrics, and don't carry over between the two files either, as the numbers above show (e.g. `co2_emissions_total_kt`'s national "high" threshold, 1250, is barely above CA's national-scale "low" threshold, 680 — California's own large counties skew high relative to the rest of the country). Re-check `MIN`/`MAX`/`AVG`/quartiles against fresh data before reusing any of these numbers elsewhere.

Eviction (2017) and Food Desert (2019) intentionally use different years than the other three (2022) — both sources' data simply doesn't extend that far; see `README.md`'s Running the pipeline section. CO2 Emissions is also the only **total**, not a rate — it reads as "where emissions concentrate," not "emissions per resident," since it isn't normalized by population.

In the California file, the map view (`view.lat`/`view.lon`/`view.zoom` in each panel's `vizConfig`) is a California-scale camera position (`lat: 37.4, lon: -118.5, zoom: 4.87`); in the US file, it's a continental-US position (`lat: 39.5, lon: -98.35, zoom: 3.8`). The panels' SQL queries have no state filter at all in either file — they render whatever's in `counties`/`county_metrics`, and the GeoJSON `src` differs only by which boundaries file it points to (`county-boundaries.geojson` vs. `county-boundaries-us.geojson`). So the queries themselves never needed to change for the US copy.

## Adding a new Geomap layer for another metric

Every metric baked into `boundaries/county-boundaries.geojson` is available as a feature property to style by. To add a new panel, prefer editing the JSON directly (see Updating above) over UI duplication:

1. Copy an existing panel's block in `spec.elements` (e.g. `panel-5`), give it a new key (e.g. `panel-6`) and a new `spec.id`.
2. Retitle it to `<Metric Name> by County (<scope>, <year>)`.
3. Update its SQL query: `SELECT c.name, c.lat, c.lon, m.value AS <metric> FROM counties c JOIN county_metrics m ON m.fips = c.fips WHERE m.metric = '<metric>' AND m.year = <year>`. The map's fill color doesn't actually depend on this query (it reads the GeoJSON's baked properties directly), but the tooltip/data table does, so a stale query silently shows the wrong values on hover.
4. Update the layer's `rules` — change every rule's `check.property` to the new metric, and rescale `check.value` thresholds to that metric's own range. Pull real `MIN/MAX/AVG`/quartiles from Postgres first rather than guessing or reusing another metric's numbers (see the table above for the pattern). Keep the first rule as the null-data check (`{operation: "eq", property: "<metric>", value: null}`, `opacity: 0`) — just update its `property` too.
5. Add a `GridLayoutItem` for the new panel in `spec.layout.spec.items`, positioned alongside the others so they render together for visual co-occurrence comparison.
6. Import via JSON Model (see Updating above), confirm it rendered correctly, then commit.

All five datasets from `project.md` now have a panel; this recipe is for whenever a sixth dataset gets added to the pipeline (see `README.md`'s "Adding a new dataset" section).
