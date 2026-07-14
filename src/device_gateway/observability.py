"""OTel observability helpers for device-gateway.

When ``monitoring.enabled`` is true in the service config, registers a
``SpanProcessor`` that copies
``oqtopus.*`` baggage entries onto every span as attributes. The baggage is
attached upstream by oqtopus-engine when it opens the per-job root span, so
this enrichment makes TraceQL lookups like ``{ .oqtopus.job_id = "..." }``
work for spans emitted on this server's side of the gRPC boundary.

The TracerProvider itself is initialised by the ``opentelemetry-instrument``
auto-instrumentation entrypoint (``backend-setup/.../otel-entrypoint.sh``);
this module does not configure exporters or the SDK.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import SpanProcessor

if TYPE_CHECKING:
    from opentelemetry.context import Context
    from opentelemetry.sdk.trace import Span

logger = logging.getLogger(__name__)

_BAGGAGE_PREFIX = "oqtopus."


class JobBaggageSpanProcessor(SpanProcessor):
    """Copy ``oqtopus.*`` baggage keys onto span attributes on span start."""

    def on_start(  # noqa: PLR6301
        self, span: Span, parent_context: Context | None = None
    ) -> None:
        """Mirror ``oqtopus.*`` baggage entries onto the starting span."""
        ctx = parent_context if parent_context is not None else context.get_current()
        for key, value in baggage.get_all(ctx).items():
            if key.startswith(_BAGGAGE_PREFIX) and value is not None:
                span.set_attribute(key, value)  # type: ignore[arg-type]


def setup_observability(config: dict[str, Any]) -> None:
    """Register ``JobBaggageSpanProcessor`` when ``monitoring.enabled`` is true."""
    if not (config.get("monitoring") or {}).get("enabled", False):
        return
    provider = trace.get_tracer_provider()
    add_span_processor = getattr(provider, "add_span_processor", None)
    if add_span_processor is None:
        logger.info(
            "tracer provider does not support add_span_processor; "
            "oqtopus.* baggage enrichment will not be active",
            extra={"provider": type(provider).__name__},
        )
        return
    add_span_processor(JobBaggageSpanProcessor())
    logger.info("JobBaggageSpanProcessor registered")
