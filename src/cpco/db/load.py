from pathlib import Path

import pandas as pd
from opentelemetry import trace
from sqlalchemy import text
from sqlalchemy.engine import Engine

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

UPSERT_SQL = text(
    """
    INSERT INTO county_metrics (fips, metric, year, value, source)
    VALUES (:fips, :metric, :year, :value, :source)
    ON CONFLICT (fips, metric, year)
    DO UPDATE SET value = excluded.value, source = excluded.source
    """
)

tracer = trace.get_tracer(__name__)


def init_schema(engine: Engine) -> None:
    with tracer.start_as_current_span("db.init_schema"):
        with engine.begin() as conn:
            conn.execute(text(SCHEMA_PATH.read_text()))


def upsert_metrics(df: pd.DataFrame, engine: Engine) -> None:
    with tracer.start_as_current_span("db.upsert_metrics", attributes={"row_count": len(df)}):
        with engine.begin() as conn:
            conn.execute(UPSERT_SQL, df.to_dict(orient="records"))
