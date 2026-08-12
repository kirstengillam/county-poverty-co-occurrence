import geopandas as gpd


def fetch(state_fips: str) -> gpd.GeoDataFrame:
    """County boundary polygons from Census TIGER/Line for the target state."""
    raise NotImplementedError


def to_geojson(gdf: gpd.GeoDataFrame, out_path: str) -> None:
    """Write county boundaries to static GeoJSON for Grafana Geomap to render."""
    raise NotImplementedError
