import pandas as pd
import requests
from opentelemetry import trace

from cpco.config import BLS_API_KEY

LAUS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
UNEMPLOYMENT_RATE_MEASURE_CODE = "03"
ANNUAL_AVERAGE_PERIOD = "M13"
MAX_SERIES_PER_REQUEST = 50  # BLS API v2 limit for registered keys

tracer = trace.get_tracer(__name__)


def _series_id(fips: str) -> str:
    state, county = fips[:2], fips[2:]
    return f"LAUCN{state}{county}00000000{UNEMPLOYMENT_RATE_MEASURE_CODE}"


def _batches(fips_codes: list[str], size: int) -> list[list[str]]:
    return [fips_codes[i : i + size] for i in range(0, len(fips_codes), size)]


def fetch(fips_codes: list[str], year: int) -> pd.DataFrame:
    """Unemployment rate from BLS LAUS, keyed by fips/metric/year/value/source."""
    with tracer.start_as_current_span(
        "etl.laus.fetch", attributes={"county_count": len(fips_codes), "year": year}
    ) as span:
        rows = []
        for batch in _batches(fips_codes, MAX_SERIES_PER_REQUEST):
            series_to_fips = {_series_id(fips): fips for fips in batch}
            payload = {
                "seriesid": list(series_to_fips),
                "startyear": str(year),
                "endyear": str(year),
                "annualaverage": True,
                "registrationkey": BLS_API_KEY,
            }
            response = requests.post(LAUS_API_URL, json=payload, timeout=30)
            response.raise_for_status()
            body = response.json()
            if body["status"] != "REQUEST_SUCCEEDED":
                raise RuntimeError(f"BLS API request failed: {body['message']}")

            for series in body["Results"]["series"]:
                annual = next((d for d in series["data"] if d["period"] == ANNUAL_AVERAGE_PERIOD), None)
                if annual is None:
                    continue
                rows.append(
                    {
                        "fips": series_to_fips[series["seriesID"]],
                        "metric": "unemployment_rate",
                        "year": year,
                        "value": float(annual["value"]),
                        "source": "bls_laus",
                    }
                )

        result = pd.DataFrame(rows, columns=["fips", "metric", "year", "value", "source"])
        span.set_attribute("row_count", len(result))
        return result
