from cpco.config import TARGET_STATE_FIPS
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import vulcan_co2
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main() -> None:
    with tracer.start_as_current_span("run_vulcan_co2", attributes={"state_fips": TARGET_STATE_FIPS}):
        engine = get_engine()
        init_schema(engine)

        df = vulcan_co2.fetch(state_fips=TARGET_STATE_FIPS)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for state {TARGET_STATE_FIPS}, year {vulcan_co2.YEAR}")


if __name__ == "__main__":
    main()
