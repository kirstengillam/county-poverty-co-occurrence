import geopandas as gpd
import pandas as pd


def fetch_raster(year: int) -> str:
    """Download the Vulcan v4.0 gridded CO2 raster for a given year, return local path."""
    raise NotImplementedError


def zonal_stats_to_county(raster_path: str, county_boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """Sum emissions within each county polygon, keyed by fips/metric/year/value/source."""
    raise NotImplementedError
