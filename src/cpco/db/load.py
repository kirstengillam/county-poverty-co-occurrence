from pathlib import Path

import pandas as pd
from opentelemetry import trace
from sqlalchemy import text
from sqlalchemy.engine import Engine

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

UPSERT_METRICS_SQL = text(
    """
    INSERT INTO county_metrics (fips, metric, year, value, source)
    VALUES (:fips, :metric, :year, :value, :source)
    ON CONFLICT (fips, metric, year)
    DO UPDATE SET value = excluded.value, source = excluded.source
    """
)

UPSERT_COUNTIES_SQL = text(
    """
    INSERT INTO counties (fips, name, lat, lon)
    VALUES (:fips, :name, :lat, :lon)
    ON CONFLICT (fips)
    DO UPDATE SET name = excluded.name, lat = excluded.lat, lon = excluded.lon
    """
)

tracer = trace.get_tracer(__name__)


def init_schema(engine: Engine) -> None:
    with tracer.start_as_current_span("db.init_schema"):
        with engine.begin() as conn:
            for statement in SCHEMA_PATH.read_text().split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))


def upsert_metrics(df: pd.DataFrame, engine: Engine) -> None:
    with tracer.start_as_current_span("db.upsert_metrics", attributes={"row_count": len(df)}):
        with engine.begin() as conn:
            conn.execute(UPSERT_METRICS_SQL, df.to_dict(orient="records"))


def upsert_counties(df: pd.DataFrame, engine: Engine) -> None:
    with tracer.start_as_current_span("db.upsert_counties", attributes={"row_count": len(df)}):
        with engine.begin() as conn:
            conn.execute(UPSERT_COUNTIES_SQL, df[["fips", "name", "lat", "lon"]].to_dict(orient="records"))
