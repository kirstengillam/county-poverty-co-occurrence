from unittest.mock import Mock, patch

from cpco.etl import eviction_lab

FAKE_CSV = """state,county,fips_state,fips_county,year,renting_hh,filings_observed,ind_filings_court_issued_lt,hh_threat_observed
California,Alameda County,6,6001,2017,281831,4123,0,
California,Alpine County,6,6003,2017,132,1,0,
California,Alameda County,6,6001,2016,278000,4000,0,
Arizona,Apache County,4,4001,2017,3000,50,0,
"""


def test_fetch_computes_filing_rate_for_target_state_and_year(tmp_path, monkeypatch):
    monkeypatch.setattr(eviction_lab, "DATA_RAW_DIR", tmp_path)
    (tmp_path / eviction_lab.COURT_ISSUED_FILENAME).write_text(FAKE_CSV)

    df = eviction_lab.fetch(state_fips="06", year=2017)

    assert list(df.columns) == ["fips", "metric", "year", "value", "source"]
    assert set(df["fips"]) == {"06001", "06003"}
    assert (df["metric"] == "eviction_filing_rate").all()
    assert (df["year"] == 2017).all()
    assert (df["source"] == "eviction_lab").all()

    alameda = df[df["fips"] == "06001"].iloc[0]
    assert round(alameda["value"], 4) == round(4123 / 281831 * 100, 4)


def test_fetch_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(eviction_lab, "DATA_RAW_DIR", tmp_path)

    with patch("cpco.etl.eviction_lab.requests.get") as mock_get:
        mock_get.return_value = Mock(content=FAKE_CSV.encode(), raise_for_status=lambda: None)
        df = eviction_lab.fetch(state_fips="06", year=2017)

    mock_get.assert_called_once()
    assert (tmp_path / eviction_lab.COURT_ISSUED_FILENAME).exists()
    assert len(df) == 2


def test_fetch_returns_every_state_when_none(tmp_path, monkeypatch):
    monkeypatch.setattr(eviction_lab, "DATA_RAW_DIR", tmp_path)
    (tmp_path / eviction_lab.COURT_ISSUED_FILENAME).write_text(FAKE_CSV)

    df = eviction_lab.fetch(state_fips=None, year=2017)

    assert set(df["fips"]) == {"06001", "06003", "04001"}
