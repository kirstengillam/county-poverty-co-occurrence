import zipfile
from pathlib import Path

import pandas as pd
import requests
from opentelemetry import trace

DATA_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

FARA_ZIP_URL = (
    "https://ers.usda.gov/media/5627/"
    "2019-large-retailer-access-map-lram-formerly-known-as-the-food-access-research-atlas-fara-data.zip"
)
FARA_ZIP_FILENAME = "food_access_research_atlas_2019.zip"
FARA_CSV_NAME = "Food Access Research Atlas.csv"

# USDA's LRAM/FARA 2019 release: supermarket list from 2019, population from the 2010 Decennial
# Census, and low-income tract classification from the 2014-18 ACS. One fixed vintage - the
# source has no per-year API, unlike SAIPE/LAUS.
YEAR = 2019

tracer = trace.get_tracer(__name__)


def fetch(state_fips: str | None) -> pd.DataFrame:
    """Tract-level food access indicators from USDA's Food Access Research Atlas.

    Pass a 2-digit state FIPS to filter to one state, or None for every state.
    """
    with tracer.start_as_current_span(
        "etl.food_access.fetch", attributes={"state_fips": state_fips or "all"}
    ) as span:
        zip_path = DATA_RAW_DIR / FARA_ZIP_FILENAME
        span.set_attribute("cached", zip_path.exists())
        if not zip_path.exists():
            DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
            response = requests.get(FARA_ZIP_URL, timeout=120)
            response.raise_for_status()
            zip_path.write_bytes(response.content)

        with zipfile.ZipFile(zip_path) as zf, zf.open(FARA_CSV_NAME) as f:
            df = pd.read_csv(f, dtype={"CensusTract": str}, usecols=["CensusTract", "Pop2010", "LILATracts_1And10"])

        # Tract GEOID is state(2) + county(3) + tract(6); slicing it gives the county FIPS
        # directly, so no spatial join is needed to roll tracts up to counties.
        df["fips"] = df["CensusTract"].str.zfill(11).str[:5]
        if state_fips is not None:
            df = df[df["fips"].str[:2] == state_fips]
        result = df[["fips", "Pop2010", "LILATracts_1And10"]].reset_index(drop=True)
        span.set_attribute("row_count", len(result))
        return result


def aggregate_to_county(tract_df: pd.DataFrame) -> pd.DataFrame:
    """Population-weighted tract -> county rollup, keyed by fips/metric/year/value/source.

    Metric is the share of county population living in a tract USDA classifies as both
    low-income and low-access to a supermarket ("LILATracts_1And10" - 1 mile urban / 10 miles
    rural) - the standard USDA definition of a food desert.
    """
    with tracer.start_as_current_span(
        "etl.food_access.aggregate_to_county", attributes={"tract_count": len(tract_df)}
    ) as span:
        low_access_pop = tract_df["Pop2010"] * tract_df["LILATracts_1And10"]
        county = tract_df.assign(low_access_pop=low_access_pop).groupby("fips").agg(
            low_access_pop=("low_access_pop", "sum"),
            total_pop=("Pop2010", "sum"),
        )
        county["value"] = county["low_access_pop"] / county["total_pop"] * 100

        result = county.reset_index()[["fips", "value"]]
        result["metric"] = "food_desert_population_share"
        result["year"] = YEAR
        result["source"] = "usda_food_access"
        result = result[["fips", "metric", "year", "value", "source"]]
        span.set_attribute("row_count", len(result))
        return result
