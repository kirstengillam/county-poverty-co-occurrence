from cpco.db.connection import get_engine
from cpco.db.load import fetch_county_fips, init_schema, upsert_metrics
from cpco.etl import laus
from cpco.telemetry.otel import configure_tracing

tracer = configure_tracing()


def main(year: int = 2022) -> None:
    # Unlike the other fetchers, LAUS has no state_fips of its own to filter on - it just
    # queries BLS for whatever county FIPS codes are already in the counties table. So its
    # scope always follows run_boundaries.py's, run with or without --nationwide.
    with tracer.start_as_current_span("run_laus", attributes={"year": year}):
        engine = get_engine()
        init_schema(engine)

        fips_codes = fetch_county_fips(engine)
        if not fips_codes:
            raise RuntimeError("No counties found in Postgres — run scripts/run_boundaries.py first")

        df = laus.fetch(fips_codes=fips_codes, year=year)
        upsert_metrics(df, engine)
        print(f"Loaded {len(df)} rows for {len(fips_codes)} counties, year {year}")


if __name__ == "__main__":
    main()
