from cpco.cli import resolve_state_fips
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import eviction_lab
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main(year: int = 2017) -> None:
    # 2017 is the most recent year with eviction filing data for every California county in
    # Eviction Lab's source file (which only covers 2000-2018) - see eviction_lab.fetch's
    # docstring. Nationwide, coverage is inherently patchy regardless of year.
    state_fips = resolve_state_fips()
    with tracer.start_as_current_span(
        "run_eviction_lab", attributes={"state_fips": state_fips or "all", "year": year}
    ):
        engine = get_engine()
        init_schema(engine)
        df = eviction_lab.fetch(state_fips=state_fips, year=year)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for state {state_fips or 'all'}, year {year}")


if __name__ == "__main__":
    main()
