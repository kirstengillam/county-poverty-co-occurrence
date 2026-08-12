import pandas as pd


def fetch(state_fips: str) -> pd.DataFrame:
    """Unemployment rate from BLS LAUS, keyed by fips/metric/year/value/source."""
    raise NotImplementedError
