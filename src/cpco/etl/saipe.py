import pandas as pd


def fetch(state_fips: str) -> pd.DataFrame:
    """Poverty rate & median household income from Census SAIPE, keyed by fips/metric/year/value/source."""
    raise NotImplementedError
