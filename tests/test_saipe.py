from unittest.mock import Mock, patch

from cpco.etl import saipe

FAKE_RESPONSE = [
    ["NAME", "SAEPOVRTALL_PT", "SAEMHI_PT", "state", "county"],
    ["Alameda County, California", "9.8", "104888", "06", "001"],
    ["Alpine County, California", "12.1", "72083", "06", "003"],
]


@patch("cpco.etl.saipe.requests.get")
def test_fetch_returns_long_format(mock_get):
    mock_get.return_value = Mock(json=lambda: FAKE_RESPONSE, raise_for_status=lambda: None)

    df = saipe.fetch(state_fips="06", year=2022)

    assert list(df.columns) == ["fips", "metric", "year", "value", "source"]
    assert len(df) == 4
    assert set(df["fips"]) == {"06001", "06003"}
    assert set(df["metric"]) == {"poverty_rate", "median_household_income"}
    row = df[(df["fips"] == "06001") & (df["metric"] == "poverty_rate")].iloc[0]
    assert row["value"] == 9.8
    assert row["year"] == 2022
    assert row["source"] == "census_saipe"


@patch("cpco.etl.saipe.requests.get")
def test_fetch_uses_wildcard_state_when_none(mock_get):
    mock_get.return_value = Mock(json=lambda: FAKE_RESPONSE, raise_for_status=lambda: None)

    saipe.fetch(state_fips=None, year=2022)

    params = mock_get.call_args.kwargs["params"]
    assert params["in"] == "state:*"
