import pandas as pd


def fetch(state_fips: str) -> pd.DataFrame:
    """Food access indicators from USDA Food Access Research Atlas, tract-level."""
    raise NotImplementedError


def aggregate_to_county(tract_df: pd.DataFrame) -> pd.DataFrame:
    """Population-weighted tract -> county rollup, keyed by fips/metric/year/value/source."""
    raise NotImplementedError
