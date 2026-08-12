import pandas as pd
from sqlalchemy import create_engine, text

from cpco.db.load import init_schema, upsert_metrics


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
