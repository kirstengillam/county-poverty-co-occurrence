from unittest.mock import Mock, patch

from cpco.etl import laus

FAKE_RESPONSE = {
    "status": "REQUEST_SUCCEEDED",
    "message": [],
    "Results": {
        "series": [
            {
                "seriesID": "LAUCN060010000000003",
                "data": [
                    {"year": "2022", "period": "M13", "periodName": "Annual", "value": "3.4", "footnotes": []},
                    {"year": "2022", "period": "M12", "periodName": "December", "value": "3.6", "footnotes": []},
                ],
            },
            {
                "seriesID": "LAUCN060030000000003",
                "data": [
                    {"year": "2022", "period": "M13", "periodName": "Annual", "value": "5.1", "footnotes": []},
                ],
            },
        ]
    },
}


@patch("cpco.etl.laus.requests.post")
def test_fetch_returns_long_format(mock_post):
    mock_post.return_value = Mock(json=lambda: FAKE_RESPONSE, raise_for_status=lambda: None)

    df = laus.fetch(fips_codes=["06001", "06003"], year=2022)

    assert list(df.columns) == ["fips", "metric", "year", "value", "source"]
    assert len(df) == 2
    row = df[df["fips"] == "06001"].iloc[0]
    assert row["metric"] == "unemployment_rate"
    assert row["value"] == 3.4
    assert row["year"] == 2022
    assert row["source"] == "bls_laus"

    payload = mock_post.call_args.kwargs["json"]
    assert payload["seriesid"] == ["LAUCN060010000000003", "LAUCN060030000000003"]
    assert payload["startyear"] == "2022"
    assert payload["endyear"] == "2022"


@patch("cpco.etl.laus.requests.post")
def test_fetch_skips_series_without_annual_average(mock_post):
    response = {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": "LAUCN060010000000003",
                    "data": [{"year": "2022", "period": "M12", "periodName": "December", "value": "3.6"}],
                }
            ]
        },
    }
    mock_post.return_value = Mock(json=lambda: response, raise_for_status=lambda: None)

    df = laus.fetch(fips_codes=["06001"], year=2022)

    assert len(df) == 0


@patch("cpco.etl.laus.requests.post")
def test_fetch_batches_series_ids(mock_post):
    mock_post.return_value = Mock(
        json=lambda: {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": []}},
        raise_for_status=lambda: None,
    )

    fips_codes = [f"06{i:03d}" for i in range(1, 76)]  # 75 counties, exceeds the 50-series batch limit
    laus.fetch(fips_codes=fips_codes, year=2022)

    assert mock_post.call_count == 2
    first_batch = mock_post.call_args_list[0].kwargs["json"]["seriesid"]
    second_batch = mock_post.call_args_list[1].kwargs["json"]["seriesid"]
    assert len(first_batch) == 50
    assert len(second_batch) == 25
