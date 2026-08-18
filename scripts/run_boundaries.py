from pathlib import Path

from cpco.cli import resolve_state_fips
from cpco.db.connection import get_engine
from cpco.db.load import fetch_metrics_wide_latest, init_schema, upsert_counties
from cpco.etl import boundaries
from cpco.telemetry.otel import configure_tracing

BOUNDARIES_DIR = Path(__file__).resolve().parents[1] / "boundaries"

tracer = configure_tracing()


def main() -> None:
    state_fips = resolve_state_fips()
    suffix = "-us" if state_fips is None else ""
    plain_out_path = BOUNDARIES_DIR / f"county-boundaries{suffix}-plain.geojson"
    baked_out_path = BOUNDARIES_DIR / f"county-boundaries{suffix}.geojson"

    with tracer.start_as_current_span("run_boundaries", attributes={"state_fips": state_fips or "all"}):
        gdf = boundaries.fetch(state_fips=state_fips)

        engine = get_engine()
        init_schema(engine)
        upsert_counties(gdf, engine)
        print(f"Loaded {len(gdf)} county centroids for state {state_fips or 'all'} into Postgres")

        plain_out_path.unlink(missing_ok=True)
        boundaries.to_geojson(gdf, str(plain_out_path))
        print(f"Wrote {len(gdf)} plain county boundaries (no baked values) to {plain_out_path}")

        metrics_df = fetch_metrics_wide_latest(engine)
        gdf_baked = gdf.merge(metrics_df, on="fips", how="left")

        baked_out_path.unlink(missing_ok=True)
        boundaries.to_geojson(gdf_baked, str(baked_out_path))
        print(
            f"Wrote {len(gdf_baked)} county boundaries for state {state_fips or 'all'} "
            f"(each metric using its own latest loaded year) to {baked_out_path}"
        )


if __name__ == "__main__":
    main()
