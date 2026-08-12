from pathlib import Path

from cpco.config import TARGET_STATE_FIPS
from cpco.etl import boundaries
from cpco.telemetry.otel import configure_tracing

OUT_PATH = Path(__file__).resolve().parents[1] / "boundaries" / "county-boundaries.geojson"

tracer = configure_tracing()


def main() -> None:
    with tracer.start_as_current_span("run_boundaries", attributes={"state_fips": TARGET_STATE_FIPS}):
        gdf = boundaries.fetch(state_fips=TARGET_STATE_FIPS)
        OUT_PATH.unlink(missing_ok=True)
        boundaries.to_geojson(gdf, str(OUT_PATH))
        print(f"Wrote {len(gdf)} county boundaries for state {TARGET_STATE_FIPS} to {OUT_PATH}")


if __name__ == "__main__":
    main()
