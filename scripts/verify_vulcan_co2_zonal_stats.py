"""Local-only sanity check: compute county CO2 totals directly from the raw 1km raster via
zonal statistics, and compare against Vulcan's own official pre-aggregated county file.

Not part of the production pipeline and produces no output that gets committed or published -
see vulcan_co2.py's module docstring for why (the raw raster is CC BY-NC-ND licensed). This is
purely the hands-on geopandas/rasterstats exercise plus a correctness check on both paths.
"""

from cpco.config import TARGET_STATE_FIPS
from cpco.etl import boundaries, vulcan_co2


def main(year: int = vulcan_co2.YEAR) -> None:
    boundaries_gdf = boundaries.fetch(state_fips=TARGET_STATE_FIPS)
    raster_path = vulcan_co2.fetch_raster(year=year)
    computed = vulcan_co2.compute_zonal_stats(boundaries_gdf, raster_path)

    official = vulcan_co2.fetch(state_fips=TARGET_STATE_FIPS)[["fips", "value"]].rename(columns={"value": "official_kt"})

    comparison = computed.merge(official, on="fips").merge(boundaries_gdf[["fips", "name"]], on="fips")
    comparison["pct_diff"] = (
        (comparison["co2_emissions_total_kt"] - comparison["official_kt"]) / comparison["official_kt"] * 100
    )
    comparison = comparison.sort_values("official_kt", ascending=False)

    print(comparison[["name", "official_kt", "co2_emissions_total_kt", "pct_diff"]].to_string(index=False))
    print(f"\nMean absolute % difference: {comparison['pct_diff'].abs().mean():.2f}%")


if __name__ == "__main__":
    main()
