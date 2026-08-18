from cpco.config import TARGET_STATE_FIPS
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import eviction_lab
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main(year: int = 2017) -> None:
    # 2017 is the most recent year with eviction filing data for every California county in
    # Eviction Lab's source file (which only covers 2000-2018) - see eviction_lab.fetch's docstring.
    with tracer.start_as_current_span("run_eviction_lab", attributes={"state_fips": TARGET_STATE_FIPS, "year": year}):
        engine = get_engine()
        init_schema(engine)
        df = eviction_lab.fetch(state_fips=TARGET_STATE_FIPS, year=year)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for state {TARGET_STATE_FIPS}, year {year}")


if __name__ == "__main__":
    main()
