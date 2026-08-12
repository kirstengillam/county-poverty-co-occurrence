import pandas as pd
import requests
from opentelemetry import trace

from cpco.config import CENSUS_API_KEY

SAIPE_API_URL = "https://api.census.gov/data/timeseries/poverty/saipe"

VARIABLES = {
    "SAEPOVRTALL_PT": "poverty_rate",
    "SAEMHI_PT": "median_household_income",
}

tracer = trace.get_tracer(__name__)


def fetch(state_fips: str, year: int) -> pd.DataFrame:
    """Poverty rate & median household income from Census SAIPE, keyed by fips/metric/year/value/source."""
    with tracer.start_as_current_span(
        "etl.saipe.fetch", attributes={"state_fips": state_fips, "year": year}
    ) as span:
        params = {
            "get": f"NAME,{','.join(VARIABLES)}",
            "for": "county:*",
            "in": f"state:{state_fips}",
            "time": year,
            "key": CENSUS_API_KEY,
        }
        response = requests.get(SAIPE_API_URL, params=params, timeout=30)
        response.raise_for_status()

        header, *records = response.json()
        df = pd.DataFrame(records, columns=header)
        df["fips"] = df["state"] + df["county"]

        long_df = df.melt(
            id_vars=["fips"],
            value_vars=list(VARIABLES),
            var_name="census_variable",
            value_name="value",
        )
        long_df["metric"] = long_df["census_variable"].map(VARIABLES)
        long_df["value"] = pd.to_numeric(long_df["value"])
        long_df["year"] = year
        long_df["source"] = "census_saipe"

        result = long_df[["fips", "metric", "year", "value", "source"]]
        span.set_attribute("row_count", len(result))
        return result
