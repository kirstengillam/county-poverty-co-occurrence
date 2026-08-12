from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from cpco.config import OTEL_EXPORTER_OTLP_ENDPOINT


def configure_tracing(service_name: str = "cpco-etl") -> trace.Tracer:
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
