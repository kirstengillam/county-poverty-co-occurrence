from pathlib import Path

import pandas as pd
import requests
from opentelemetry import trace

DATA_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

COURT_ISSUED_URL = "https://eviction-lab-data-downloads.s3.amazonaws.com/data-for-analysis/county_court-issued_2000_2018.csv"
COURT_ISSUED_FILENAME = "eviction_lab_county_court-issued_2000_2018.csv"

tracer = trace.get_tracer(__name__)


def fetch(state_fips: str | None, year: int) -> pd.DataFrame:
    """Eviction filing rate from Eviction Lab, keyed by fips/metric/year/value/source.

    Pass a 2-digit state FIPS to filter to one state, or None for every state. Source data only
    covers 2000-2018 (last update to this Eviction Lab file), so `year` must be one with usable
    county coverage — 2017 is the most recent year with data for every California county, but
    nationwide, coverage is inherently patchy: many jurisdictions never had court eviction
    records collected at all, not just missing recent years, so expect gaps in the result
    regardless of which year is chosen.
    """
    with tracer.start_as_current_span(
        "etl.eviction_lab.fetch", attributes={"state_fips": state_fips or "all", "year": year}
    ) as span:
        csv_path = DATA_RAW_DIR / COURT_ISSUED_FILENAME
        span.set_attribute("cached", csv_path.exists())
        if not csv_path.exists():
            DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
            response = requests.get(COURT_ISSUED_URL, timeout=60)
            response.raise_for_status()
            csv_path.write_bytes(response.content)

        df = pd.read_csv(csv_path, dtype={"fips_county": str})
        df["fips"] = df["fips_county"].str.zfill(5)
        if state_fips is not None:
            df = df[df["fips"].str[:2] == state_fips]
        subset = df[df["year"] == year].copy()

        result = pd.DataFrame(
            {
                "fips": subset["fips"],
                "metric": "eviction_filing_rate",
                "year": year,
                "value": subset["filings_observed"] / subset["renting_hh"] * 100,
                "source": "eviction_lab",
            }
        ).reset_index(drop=True)
        span.set_attribute("row_count", len(result))
        return result
