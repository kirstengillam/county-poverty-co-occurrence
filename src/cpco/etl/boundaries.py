from pathlib import Path

import geopandas as gpd
import requests

DATA_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

TIGER_COUNTY_URL_TEMPLATE = "https://www2.census.gov/geo/tiger/TIGER{year}/COUNTY/tl_{year}_us_county.zip"


def fetch(state_fips: str, year: int = 2023) -> gpd.GeoDataFrame:
    """County boundary polygons from Census TIGER/Line for the target state."""
    zip_path = DATA_RAW_DIR / f"tl_{year}_us_county.zip"
    if not zip_path.exists():
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        response = requests.get(TIGER_COUNTY_URL_TEMPLATE.format(year=year), timeout=120)
        response.raise_for_status()
        zip_path.write_bytes(response.content)

    counties = gpd.read_file(zip_path)
    state_counties = counties[counties["STATEFP"] == state_fips]

    return state_counties.rename(columns={"GEOID": "fips", "NAME": "name"})[["fips", "name", "geometry"]]


def to_geojson(gdf: gpd.GeoDataFrame, out_path: str) -> None:
    """Write county boundaries to static GeoJSON for Grafana Geomap to render."""
    gdf.to_crs(epsg=4326).to_file(out_path, driver="GeoJSON")
