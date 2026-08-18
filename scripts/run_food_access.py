from cpco.cli import resolve_state_fips
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import food_access
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main() -> None:
    state_fips = resolve_state_fips()
    with tracer.start_as_current_span("run_food_access", attributes={"state_fips": state_fips or "all"}):
        engine = get_engine()
        init_schema(engine)

        tract_df = food_access.fetch(state_fips=state_fips)
        df = food_access.aggregate_to_county(tract_df)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} county rows for state {state_fips or 'all'} from {len(tract_df)} tracts")


if __name__ == "__main__":
    main()
