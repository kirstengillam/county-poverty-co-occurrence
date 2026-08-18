from cpco import cli


def test_resolve_state_fips_defaults_to_target_state(monkeypatch):
    monkeypatch.setattr(cli, "TARGET_STATE_FIPS", "06")
    monkeypatch.setattr("sys.argv", ["run_saipe.py"])

    assert cli.resolve_state_fips() == "06"


def test_resolve_state_fips_returns_none_when_nationwide_flag_set(monkeypatch):
    monkeypatch.setattr(cli, "TARGET_STATE_FIPS", "06")
    monkeypatch.setattr("sys.argv", ["run_saipe.py", "--nationwide"])

    assert cli.resolve_state_fips() is None
