import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/cpco")
TARGET_STATE_FIPS = os.environ.get("TARGET_STATE_FIPS")

OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_EXPORTER_OTLP_HEADERS = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS")
