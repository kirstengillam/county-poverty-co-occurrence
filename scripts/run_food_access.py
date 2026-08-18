from cpco.config import TARGET_STATE_FIPS
from cpco.db.connection import get_engine
from cpco.db.load import init_schema, upsert_metrics
from cpco.etl import food_access
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main() -> None:
    with tracer.start_as_current_span("run_food_access", attributes={"state_fips": TARGET_STATE_FIPS}):
        engine = get_engine()
        init_schema(engine)

        tract_df = food_access.fetch(state_fips=TARGET_STATE_FIPS)
        df = food_access.aggregate_to_county(tract_df)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} county rows for state {TARGET_STATE_FIPS} from {len(tract_df)} tracts")


if __name__ == "__main__":
    main()
