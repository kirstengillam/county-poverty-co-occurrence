from cpco.cli import resolve_state_fips
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import saipe
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main(year: int = 2022) -> None:
    state_fips = resolve_state_fips()
    with tracer.start_as_current_span("run_saipe", attributes={"state_fips": state_fips or "all", "year": year}):
        engine = get_engine()
        init_schema(engine)
        df = saipe.fetch(state_fips=state_fips, year=year)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for state {state_fips or 'all'}, year {year}")


if __name__ == "__main__":
    main()
