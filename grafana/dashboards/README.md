# Dashboard exports

This directory holds a version-controlled copy of the live dashboard, exported from Grafana Cloud. It's a backup/reference, not something Grafana reads — Grafana Cloud is a managed instance, so file-based provisioning (mounting this folder into Grafana's config) isn't possible here. To make this live-provisioned instead, it'd need a push mechanism such as Terraform (`grafana` provider) or the Grafana HTTP API.

## Updating

After changing the dashboard in the Grafana Cloud UI:

1. Share icon → **Export** tab → toggle "Export for sharing externally" **off** → **Save to file**.
2. Overwrite `county-poverty-geomap.json` with the downloaded file.
3. Commit.

The exported filename from Grafana includes a random ID (e.g. `County Poverty-1786992286674.json`) — rename it back to `county-poverty-geomap.json` when you overwrite.
