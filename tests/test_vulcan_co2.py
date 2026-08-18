import io
import zipfile
from unittest.mock import Mock, patch

import geopandas as gpd
import numpy as np
import openpyxl
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from cpco.etl import vulcan_co2


def _fake_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = str(vulcan_co2.YEAR)
    ws.append(["State", "County", "FIPS", "Total FFCO2 (tC)"])
    ws.append(["CA", "alameda", 6001, 1000.0])
    ws.append(["CA", "alpine", 6003, 50.0])
    ws.append(["NY", "albany", 36001, 2000.0])
    ws.append(["US (MtC)", None, None, 9999.0])  # national-total footer row, FIPS is blank
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fetch_filters_to_state_and_converts_tc_to_tco2(tmp_path, monkeypatch):
    monkeypatch.setattr(vulcan_co2, "DATA_RAW_DIR", tmp_path)
    (tmp_path / vulcan_co2.COUNTY_XLSX_FILENAME).write_bytes(_fake_xlsx_bytes())

    df = vulcan_co2.fetch(state_fips="06")

    assert list(df.columns) == ["fips", "metric", "year", "value", "source"]
    assert len(df) == 2
    assert set(df["fips"]) == {"06001", "06003"}
    assert (df["metric"] == "co2_emissions_total_kt").all()
    assert (df["year"] == vulcan_co2.YEAR).all()
    assert (df["source"] == "vulcan_co2").all()

    row = df[df["fips"] == "06001"].iloc[0]
    assert row["value"] == pytest.approx(1000.0 * (44 / 12) / 1000)


def test_fetch_returns_every_state_when_none(tmp_path, monkeypatch):
    monkeypatch.setattr(vulcan_co2, "DATA_RAW_DIR", tmp_path)
    (tmp_path / vulcan_co2.COUNTY_XLSX_FILENAME).write_bytes(_fake_xlsx_bytes())

    df = vulcan_co2.fetch(state_fips=None)

    assert set(df["fips"]) == {"06001", "06003", "36001"}


def test_fetch_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(vulcan_co2, "DATA_RAW_DIR", tmp_path)

    with patch("cpco.etl.vulcan_co2.requests.get") as mock_get:
        mock_get.return_value = Mock(content=_fake_xlsx_bytes(), raise_for_status=lambda: None)
        df = vulcan_co2.fetch(state_fips="06")

    mock_get.assert_called_once()
    assert (tmp_path / vulcan_co2.COUNTY_XLSX_FILENAME).exists()
    assert len(df) == 2


def test_fetch_raster_extracts_cached_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(vulcan_co2, "DATA_RAW_DIR", tmp_path)
    tif_name = vulcan_co2.RASTER_TIF_TEMPLATE.format(year=vulcan_co2.YEAR)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(tif_name, b"fake-tif-bytes")
    (tmp_path / vulcan_co2.RASTER_ZIP_FILENAME).write_bytes(zip_buf.getvalue())

    with patch("cpco.etl.vulcan_co2.requests.get") as mock_get:
        path = vulcan_co2.fetch_raster(year=vulcan_co2.YEAR)

    mock_get.assert_not_called()  # zip already cached, no download needed
    assert path == tmp_path / tif_name
    assert path.read_bytes() == b"fake-tif-bytes"


def test_compute_zonal_stats_sums_raster_within_polygon(tmp_path):
    transform = from_origin(0, 3, 1, 1)  # 3x3 grid of 1-degree cells, origin at (0, 3)
    data = np.full((3, 3), 10.0, dtype="float32")
    raster_path = tmp_path / "fake.tif"
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)

    gdf = gpd.GeoDataFrame({"fips": ["00001"]}, geometry=[box(0, 0, 3, 3)], crs="EPSG:4326")

    result = vulcan_co2.compute_zonal_stats(gdf, raster_path)

    assert list(result.columns) == ["fips", "co2_emissions_total_kt"]
    expected_tc = 9 * 10.0  # 9 cells x 10 tC each
    expected_kt = expected_tc * vulcan_co2.TC_TO_TCO2 / 1000
    assert result.loc[0, "co2_emissions_total_kt"] == pytest.approx(expected_kt)
