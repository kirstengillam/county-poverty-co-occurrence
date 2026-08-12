import pandas as pd


def fetch(state_fips: str) -> pd.DataFrame:
    """Eviction filings/rates from Eviction Lab, keyed by fips/metric/year/value/source."""
    raise NotImplementedError
