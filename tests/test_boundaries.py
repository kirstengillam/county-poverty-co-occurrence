from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Polygon

from cpco.etl import boundaries


def _fake_counties() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "STATEFP": ["06", "06", "04"],
            "GEOID": ["06001", "06003", "04001"],
            "NAME": ["Alameda", "Alpine", "Apache"],
            "INTPTLAT": ["+37.6017", "+38.5971", "+34.0489"],
            "INTPTLON": ["-121.7195", "-119.7896", "-109.4936"],
            "geometry": [Polygon([(0, 0), (1, 0), (1, 1)])] * 3,
        },
        crs="EPSG:4269",
    )


def test_fetch_filters_to_state_and_renames_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "DATA_RAW_DIR", tmp_path)
    (tmp_path / "tl_2023_us_county.zip").write_bytes(b"placeholder")

    with patch("cpco.etl.boundaries.gpd.read_file", return_value=_fake_counties()):
        gdf = boundaries.fetch(state_fips="06")

    assert list(gdf.columns) == ["fips", "name", "lat", "lon", "geometry"]
    assert set(gdf["fips"]) == {"06001", "06003"}
    alameda = gdf[gdf["fips"] == "06001"].iloc[0]
    assert alameda["lat"] == 37.6017
    assert alameda["lon"] == -121.7195


def test_to_geojson_reprojects_to_wgs84(tmp_path):
    gdf = _fake_counties().rename(columns={"GEOID": "fips", "NAME": "name"})[["fips", "name", "geometry"]]
    out_path = tmp_path / "county-boundaries.geojson"

    boundaries.to_geojson(gdf, str(out_path))

    result = gpd.read_file(out_path)
    assert result.crs.to_epsg() == 4326
    assert len(result) == 3
