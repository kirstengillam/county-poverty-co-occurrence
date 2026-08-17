from pathlib import Path

from cpco.config import TARGET_STATE_FIPS
from cpco.db.connection import get_engine
from cpco.db.load import fetch_metrics_wide, init_schema, upsert_counties
from cpco.etl import boundaries
from cpco.telemetry.otel import configure_tracing

BOUNDARIES_DIR = Path(__file__).resolve().parents[1] / "boundaries"
PLAIN_OUT_PATH = BOUNDARIES_DIR / "county-boundaries-plain.geojson"
BAKED_OUT_PATH = BOUNDARIES_DIR / "county-boundaries.geojson"

tracer = configure_tracing()


def main(year: int = 2022) -> None:
    with tracer.start_as_current_span(
        "run_boundaries", attributes={"state_fips": TARGET_STATE_FIPS, "year": year}
    ):
        gdf = boundaries.fetch(state_fips=TARGET_STATE_FIPS)

        engine = get_engine()
        init_schema(engine)
        upsert_counties(gdf, engine)
        print(f"Loaded {len(gdf)} county centroids for state {TARGET_STATE_FIPS} into Postgres")

        PLAIN_OUT_PATH.unlink(missing_ok=True)
        boundaries.to_geojson(gdf, str(PLAIN_OUT_PATH))
        print(f"Wrote {len(gdf)} plain county boundaries (no baked values) to {PLAIN_OUT_PATH}")

        metrics_df = fetch_metrics_wide(engine, year=year)
        gdf_baked = gdf.merge(metrics_df, on="fips", how="left")

        BAKED_OUT_PATH.unlink(missing_ok=True)
        boundaries.to_geojson(gdf_baked, str(BAKED_OUT_PATH))
        print(
            f"Wrote {len(gdf_baked)} county boundaries for state {TARGET_STATE_FIPS} "
            f"(with {year} metric values baked in) to {BAKED_OUT_PATH}"
        )


if __name__ == "__main__":
    main()
