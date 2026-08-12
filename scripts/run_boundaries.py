from pathlib import Path

from cpco.config import TARGET_STATE_FIPS
from cpco.etl import boundaries

OUT_PATH = Path(__file__).resolve().parents[1] / "boundaries" / "county-boundaries.geojson"


def main() -> None:
    gdf = boundaries.fetch(state_fips=TARGET_STATE_FIPS)
    OUT_PATH.unlink(missing_ok=True)
    boundaries.to_geojson(gdf, str(OUT_PATH))
    print(f"Wrote {len(gdf)} county boundaries for state {TARGET_STATE_FIPS} to {OUT_PATH}")


if __name__ == "__main__":
    main()
