"""CO2 emissions from the Vulcan Project v4.0 (NASA/Northern Arizona University).

The raw 1km gridded raster is licensed CC BY-NC-ND 4.0 - No Derivatives. Per the license text
(Section 2(a)), we may "reproduce and Share... in whole or in part" the Licensed Material
unmodified, but may only "produce and reproduce, but not Share" Adapted Material (anything we
transform/aggregate ourselves). So:

- `fetch()` uses Vulcan's own pre-aggregated county-level file, filtered to a state and left
  numerically unmodified - this is the "Share... in part" path, and is what's actually loaded
  into Postgres/baked into the GeoJSON/shown on the dashboard.
- `compute_zonal_stats()` computes county totals directly from the raw raster ourselves - this
  produces Adapted Material. It exists for local learning/verification only (per project.md's
  suggestion to sanity-check against the official file) and its output must never be committed,
  baked into public GeoJSON, or otherwise published. See scripts/verify_vulcan_co2_zonal_stats.py.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
import requests
from opentelemetry import trace
from rasterstats import zonal_stats

DATA_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

COUNTY_XLSX_URL = "https://zenodo.org/records/15446748/files/v4.all.co2.county.mn.allyrs.xlsx?download=1"
COUNTY_XLSX_FILENAME = "vulcan_v4_county_2010_2022.xlsx"

RASTER_ZIP_URL = "https://zenodo.org/records/15446748/files/v4.tot.co2.usa.1km.lcc.mn.allyrs.zip?download=1"
RASTER_ZIP_FILENAME = "vulcan_tot_co2_usa_1km_allyrs.zip"
RASTER_TIF_TEMPLATE = "v4.tot.co2.usa.1km.lcc.mn.{year}.tif"

# Source values are in metric tons of carbon (tC), not CO2 - see the Vulcan V4.0 readme.
# Multiply by the CO2:C molecular weight ratio to report the more commonly understood tCO2.
TC_TO_TCO2 = 44 / 12

YEAR = 2022  # most recent year in the source, matching SAIPE/LAUS

tracer = trace.get_tracer(__name__)


def fetch(state_fips: str) -> pd.DataFrame:
    """Official county-level total CO2 emissions (kilotons/year) from Vulcan's own pre-aggregated
    file, keyed by fips/metric/year/value/source. Unlike this project's other metrics, this is a
    total, not a rate - county size and industrial activity drive it, not just population.
    """
    with tracer.start_as_current_span("etl.vulcan_co2.fetch", attributes={"state_fips": state_fips}) as span:
        xlsx_path = DATA_RAW_DIR / COUNTY_XLSX_FILENAME
        span.set_attribute("cached", xlsx_path.exists())
        if not xlsx_path.exists():
            DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
            response = requests.get(COUNTY_XLSX_URL, timeout=120)
            response.raise_for_status()
            xlsx_path.write_bytes(response.content)

        df = pd.read_excel(xlsx_path, sheet_name=str(YEAR), usecols=["FIPS", "Total FFCO2 (tC)"])
        df = df.dropna(subset=["FIPS"])  # drops the national-total footer row
        df["fips"] = df["FIPS"].astype(int).astype(str).str.zfill(5)

        state_df = df[df["fips"].str[:2] == state_fips]
        result = pd.DataFrame(
            {
                "fips": state_df["fips"],
                "metric": "co2_emissions_total_kt",
                "year": YEAR,
                "value": state_df["Total FFCO2 (tC)"] * TC_TO_TCO2 / 1000,
                "source": "vulcan_co2",
            }
        ).reset_index(drop=True)
        span.set_attribute("row_count", len(result))
        return result


def fetch_raster(year: int = YEAR) -> Path:
    """Download (if not cached) and return the path to the raw 1km CO2 raster for one year.

    Local-only input for compute_zonal_stats - never used for the published metric.
    """
    tif_path = DATA_RAW_DIR / RASTER_TIF_TEMPLATE.format(year=year)
    if tif_path.exists():
        return tif_path

    zip_path = DATA_RAW_DIR / RASTER_ZIP_FILENAME
    if not zip_path.exists():
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        response = requests.get(RASTER_ZIP_URL, timeout=600)
        response.raise_for_status()
        zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extract(RASTER_TIF_TEMPLATE.format(year=year), DATA_RAW_DIR)
    return tif_path


def compute_zonal_stats(boundaries_gdf: gpd.GeoDataFrame, raster_path: Path) -> pd.DataFrame:
    """County CO2 totals (kilotons/year) computed directly from the raw raster via zonal
    statistics - local verification only, see module docstring. Returns fips/co2_emissions_total_kt,
    deliberately not the standard fips/metric/year/value/source shape used for publishable metrics.
    """
    with tracer.start_as_current_span(
        "etl.vulcan_co2.compute_zonal_stats", attributes={"county_count": len(boundaries_gdf)}
    ) as span:
        with rasterio.open(raster_path) as src:
            raster_crs = src.crs
            nodata = src.nodata

        gdf_proj = boundaries_gdf.to_crs(raster_crs)
        stats = zonal_stats(gdf_proj, str(raster_path), stats=["sum"], nodata=nodata)

        result = pd.DataFrame(
            {
                "fips": boundaries_gdf["fips"].values,
                "co2_emissions_total_kt": [
                    s["sum"] * TC_TO_TCO2 / 1000 if s["sum"] is not None else None for s in stats
                ],
            }
        )
        span.set_attribute("row_count", len(result))
        return result
