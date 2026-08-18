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


def fetch_county_fips(engine: Engine) -> list[str]:
    """All county FIPS codes currently loaded into Postgres, e.g. to build downstream API queries."""
    with tracer.start_as_current_span("db.fetch_county_fips"):
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT fips FROM counties ORDER BY fips")).fetchall()
        return [row[0] for row in rows]


def fetch_metrics_wide(engine: Engine, year: int) -> pd.DataFrame:
    """One row per fips, one column per metric, for the given year."""
    with tracer.start_as_current_span("db.fetch_metrics_wide", attributes={"year": year}):
        with engine.connect() as conn:
            long_df = pd.read_sql(
                text("SELECT fips, metric, value FROM county_metrics WHERE year = :year"),
                conn,
                params={"year": year},
            )
        return long_df.pivot(index="fips", columns="metric", values="value").reset_index()


def fetch_metrics_wide_latest(engine: Engine) -> pd.DataFrame:
    """One row per fips, one column per metric, each using that metric's own most recent year.

    Datasets land at different years (e.g. SAIPE/LAUS at 2022, Eviction Lab at 2017 - its
    source only covers through 2018), so there's no single year that covers every metric.
    """
    with tracer.start_as_current_span("db.fetch_metrics_wide_latest"):
        with engine.connect() as conn:
            long_df = pd.read_sql(
                text(
                    """
                    SELECT fips, metric, value
                    FROM county_metrics cm
                    WHERE year = (SELECT MAX(year) FROM county_metrics WHERE metric = cm.metric)
                    """
                ),
                conn,
            )
        return long_df.pivot(index="fips", columns="metric", values="value").reset_index()
