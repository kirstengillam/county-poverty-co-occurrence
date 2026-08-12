from cpco.config import TARGET_STATE_FIPS
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import saipe
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main(year: int = 2022) -> None:
    with tracer.start_as_current_span("run_saipe", attributes={"state_fips": TARGET_STATE_FIPS, "year": year}):
        engine = get_engine()
        init_schema(engine)
        df = saipe.fetch(state_fips=TARGET_STATE_FIPS, year=year)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for state {TARGET_STATE_FIPS}, year {year}")


if __name__ == "__main__":
    main()
