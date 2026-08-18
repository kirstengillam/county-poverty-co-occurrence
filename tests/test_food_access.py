import io
import zipfile
from unittest.mock import Mock, patch

import pandas as pd

from cpco.etl import food_access

FAKE_CSV = """CensusTract,Pop2010,LILATracts_1And10
06001400100,1000,1
06001400200,2000,0
06003000100,500,1
04001000100,300,1
"""


def _fake_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(food_access.FARA_CSV_NAME, FAKE_CSV)
    return buf.getvalue()


def test_fetch_filters_to_state(tmp_path, monkeypatch):
    monkeypatch.setattr(food_access, "DATA_RAW_DIR", tmp_path)
    (tmp_path / food_access.FARA_ZIP_FILENAME).write_bytes(_fake_zip_bytes())

    df = food_access.fetch(state_fips="06")

    assert list(df.columns) == ["fips", "Pop2010", "LILATracts_1And10"]
    assert len(df) == 3
    assert set(df["fips"]) == {"06001", "06003"}


def test_fetch_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(food_access, "DATA_RAW_DIR", tmp_path)

    with patch("cpco.etl.food_access.requests.get") as mock_get:
        mock_get.return_value = Mock(content=_fake_zip_bytes(), raise_for_status=lambda: None)
        df = food_access.fetch(state_fips="06")

    mock_get.assert_called_once()
    assert (tmp_path / food_access.FARA_ZIP_FILENAME).exists()
    assert len(df) == 3


def test_aggregate_to_county_population_weights_food_desert_share():
    tract_df = pd.DataFrame(
        {
            "fips": ["06001", "06001", "06003"],
            "Pop2010": [1000, 2000, 500],
            "LILATracts_1And10": [1, 0, 1],
        }
    )

    df = food_access.aggregate_to_county(tract_df)

    assert list(df.columns) == ["fips", "metric", "year", "value", "source"]
    assert (df["metric"] == "food_desert_population_share").all()
    assert (df["year"] == food_access.YEAR).all()
    assert (df["source"] == "usda_food_access").all()

    row_06001 = df[df["fips"] == "06001"].iloc[0]
    assert round(row_06001["value"], 4) == round(1000 / 3000 * 100, 4)

    row_06003 = df[df["fips"] == "06003"].iloc[0]
    assert row_06003["value"] == 100.0
