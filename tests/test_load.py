import pandas as pd
from sqlalchemy import create_engine, text

from cpco.db.load import fetch_metrics_wide, init_schema, upsert_counties, upsert_metrics


def test_init_schema_and_upsert():
    engine = create_engine("sqlite:///:memory:")
    init_schema(engine)

    df = pd.DataFrame(
        [
            {"fips": "06001", "metric": "poverty_rate", "year": 2022, "value": 10.1, "source": "census_saipe"},
            {"fips": "06003", "metric": "poverty_rate", "year": 2022, "value": 16.3, "source": "census_saipe"},
        ]
    )
    upsert_metrics(df, engine)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT fips, value FROM county_metrics ORDER BY fips")).fetchall()
    assert rows == [("06001", 10.1), ("06003", 16.3)]

    updated = pd.DataFrame(
        [{"fips": "06001", "metric": "poverty_rate", "year": 2022, "value": 11.5, "source": "census_saipe"}]
    )
    upsert_metrics(updated, engine)

    with engine.connect() as conn:
        value = conn.execute(text("SELECT value FROM county_metrics WHERE fips = '06001'")).scalar()
    assert value == 11.5


def test_upsert_counties():
    engine = create_engine("sqlite:///:memory:")
    init_schema(engine)

    df = pd.DataFrame(
        [
            {"fips": "06001", "name": "Alameda", "lat": 37.6017, "lon": -121.7195},
            {"fips": "06003", "name": "Alpine", "lat": 38.5971, "lon": -119.7896},
        ]
    )
    upsert_counties(df, engine)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT fips, name, lat, lon FROM counties ORDER BY fips")).fetchall()
    assert rows == [
        ("06001", "Alameda", 37.6017, -121.7195),
        ("06003", "Alpine", 38.5971, -119.7896),
    ]


def test_fetch_metrics_wide_pivots_metric_to_columns():
    engine = create_engine("sqlite:///:memory:")
    init_schema(engine)

    df = pd.DataFrame(
        [
            {"fips": "06001", "metric": "poverty_rate", "year": 2022, "value": 10.1, "source": "census_saipe"},
            {
                "fips": "06001",
                "metric": "median_household_income",
                "year": 2022,
                "value": 121190.0,
                "source": "census_saipe",
            },
            {"fips": "06003", "metric": "poverty_rate", "year": 2022, "value": 16.3, "source": "census_saipe"},
            {"fips": "06001", "metric": "poverty_rate", "year": 2021, "value": 9.5, "source": "census_saipe"},
        ]
    )
    upsert_metrics(df, engine)

    wide = fetch_metrics_wide(engine, year=2022).set_index("fips")

    assert set(wide.columns) == {"poverty_rate", "median_household_income"}
    assert wide.loc["06001", "poverty_rate"] == 10.1
    assert wide.loc["06001", "median_household_income"] == 121190.0
    assert pd.isna(wide.loc["06003", "median_household_income"])
