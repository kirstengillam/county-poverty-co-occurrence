from pathlib import Path

import geopandas as gpd
import requests
from opentelemetry import trace

DATA_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# Census's pre-simplified "cartographic boundary" (cb_) files, not the full-resolution
# TIGER/Line (tl_) survey files used elsewhere - full-res national county boundaries are
# ~220MB (over GitHub's 100MB push limit, and too big to render smoothly in a browser).
# The 1:5,000,000 cartographic tier keeps a national file to ~6.5MB, about what a single
# state already costs today, while staying visually accurate for county-level thematic
# mapping - exactly what these files are designed for.
CARTOGRAPHIC_COUNTY_URL_TEMPLATE = "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_county_5m.zip"

tracer = trace.get_tracer(__name__)


def fetch(state_fips: str | None = None, year: int = 2023) -> gpd.GeoDataFrame:
    """County boundary polygons from Census cartographic boundary files.

    Pass a 2-digit state FIPS to filter to one state, or None for every county /
    county-equivalent nationwide.
    """
    with tracer.start_as_current_span(
        "etl.boundaries.fetch", attributes={"state_fips": state_fips or "all", "year": year}
    ) as span:
        zip_path = DATA_RAW_DIR / f"cb_{year}_us_county_5m.zip"
        span.set_attribute("cached", zip_path.exists())
        if not zip_path.exists():
            DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
            response = requests.get(CARTOGRAPHIC_COUNTY_URL_TEMPLATE.format(year=year), timeout=120)
            response.raise_for_status()
            zip_path.write_bytes(response.content)

        counties = gpd.read_file(zip_path)
        if state_fips is not None:
            counties = counties[counties["STATEFP"] == state_fips]

        result = counties.rename(columns={"GEOID": "fips", "NAME": "name"})
        # cb_ files don't ship INTPTLAT/INTPTLON like tl_ files do. representative_point()
        # is the geometry-derived equivalent - guaranteed to fall inside the polygon, unlike
        # a naive centroid which can land outside for concave/multi-part county shapes.
        interior_point = result.geometry.representative_point()
        result["lat"] = interior_point.y
        result["lon"] = interior_point.x
        result = result[["fips", "name", "lat", "lon", "geometry"]]
        span.set_attribute("row_count", len(result))
        return result


def to_geojson(gdf: gpd.GeoDataFrame, out_path: str) -> None:
    """Write county boundaries to static GeoJSON for Grafana Geomap to render."""
    with tracer.start_as_current_span("etl.boundaries.to_geojson", attributes={"row_count": len(gdf)}):
        gdf.to_crs(epsg=4326).to_file(out_path, driver="GeoJSON")
