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
            "geometry": [
                Polygon([(-122.5, 37.5), (-121.5, 37.5), (-121.5, 38.0), (-122.5, 38.0)]),
                Polygon([(-120.0, 38.5), (-119.0, 38.5), (-119.0, 39.0), (-120.0, 39.0)]),
                Polygon([(-110.0, 34.0), (-109.0, 34.0), (-109.0, 34.5), (-110.0, 34.5)]),
            ],
        },
        crs="EPSG:4269",
    )


def test_fetch_filters_to_state_and_renames_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "DATA_RAW_DIR", tmp_path)
    (tmp_path / "cb_2023_us_county_5m.zip").write_bytes(b"placeholder")

    with patch("cpco.etl.boundaries.gpd.read_file", return_value=_fake_counties()):
        gdf = boundaries.fetch(state_fips="06")

    assert list(gdf.columns) == ["fips", "name", "lat", "lon", "geometry"]
    assert set(gdf["fips"]) == {"06001", "06003"}
    alameda = gdf[gdf["fips"] == "06001"].iloc[0]
    assert alameda["geometry"].contains(gdf[gdf["fips"] == "06001"].iloc[0]["geometry"].representative_point())
    assert -122.5 <= alameda["lon"] <= -121.5
    assert 37.5 <= alameda["lat"] <= 38.0


def test_fetch_returns_all_states_when_state_fips_none(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "DATA_RAW_DIR", tmp_path)
    (tmp_path / "cb_2023_us_county_5m.zip").write_bytes(b"placeholder")

    with patch("cpco.etl.boundaries.gpd.read_file", return_value=_fake_counties()):
        gdf = boundaries.fetch(state_fips=None)

    assert set(gdf["fips"]) == {"06001", "06003", "04001"}


def test_to_geojson_reprojects_to_wgs84(tmp_path):
    gdf = _fake_counties().rename(columns={"GEOID": "fips", "NAME": "name"})[["fips", "name", "geometry"]]
    out_path = tmp_path / "county-boundaries.geojson"

    boundaries.to_geojson(gdf, str(out_path))

    result = gpd.read_file(out_path)
    assert result.crs.to_epsg() == 4326
    assert len(result) == 3
