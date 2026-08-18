import argparse

from cpco.config import TARGET_STATE_FIPS


def resolve_state_fips() -> str | None:
    """Parses --nationwide from argv; returns None (every state) if set, else TARGET_STATE_FIPS."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--nationwide", action="store_true", help="Run for every state instead of TARGET_STATE_FIPS"
    )
    args = parser.parse_args()
    return None if args.nationwide else TARGET_STATE_FIPS
