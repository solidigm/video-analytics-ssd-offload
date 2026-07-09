# Created by Metrum AI for Solidigm

"""
Agent Telemetry using OpenTelemetry.

Provides tracing and metrics for agent execution, tool calls, and LLM/VLM requests.
Exports to: File (JSON), Console, or OTLP collector (Jaeger, Zipkin).
"""

import os
import json
import time
import functools
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Sequence
from contextlib import contextmanager

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Try to import OTLP exporter (optional - for production)
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False


# Configuration
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")  # Empty = disabled by default
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "american_football-analytics-agent")
OTEL_CONSOLE_EXPORT = os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true"
OTEL_FILE_EXPORT = os.getenv("OTEL_FILE_EXPORT", "true").lower() == "true"  # Enabled by default
OTEL_OUTPUT_DIR = os.getenv("OTEL_OUTPUT_DIR", "telemetry_output")


class FileSpanExporter(SpanExporter):
    """Export spans to JSON files with LLM performance analytics."""

    def __init__(self, output_dir: str = OTEL_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._spans = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Collect spans and flush them into the JSON trace artifact."""
        for span in spans:
            span_data = {
                "name": span.name,
                "trace_id": format(span.context.trace_id, "032x"),
                "span_id": format(span.context.span_id, "016x"),
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "duration_ms": ((span.end_time - span.start_time) / 1_000_000 if span.end_time else None),
                "status": span.status.status_code.name,
                "attributes": dict(span.attributes) if span.attributes else {},
            }
            self._spans.append(span_data)

        # Write to file
        self._write_to_file()
        return SpanExportResult.SUCCESS

    def _compute_llm_analytics(self) -> dict:
        """Compute detailed LLM performance metrics for comparison."""
        llm_spans = [s for s in self._spans if s["name"] in ["llm.call", "vlm.call"] or (s["name"] == "POST" and "chat/completions" in s.get("attributes", {}).get("http.url", ""))]

        def is_vlm_span(span: dict) -> bool:
            attrs = span.get("attributes", {})
            http_url = str(attrs.get("http.url", "")).lower()
            llm_type = attrs.get("llm.type")
            llm_model = attrs.get("llm.model")
            return llm_type == "vlm" or "vllm-vlm" in http_url or llm_model == "Qwen/Qwen3-VL-30B-A3B-Thinking"

        def is_llm_span(span: dict) -> bool:
            attrs = span.get("attributes", {})
            http_url = str(attrs.get("http.url", "")).lower()
            llm_type = attrs.get("llm.type")
            llm_model = attrs.get("llm.model")
            return llm_type == "llm" or "vllm-lmcache" in http_url or "vllm-baseline" in http_url or llm_model == "aws-prototyping/MegaBeam-Mistral-7B-300k"

        vlm_spans = [s for s in llm_spans if is_vlm_span(s)]
        llm_only_spans = [s for s in llm_spans if is_llm_span(s)]

        def compute_stats(spans):
            if not spans:
                return None
            durations = [s["duration_ms"] for s in spans if s.get("duration_ms")]
            tokens = [s.get("attributes", {}).get("llm.tokens", 0) for s in spans]
            total_tokens = sum(t for t in tokens if t)
            total_duration_sec = sum(durations) / 1000 if durations else 0

            return {
                "call_count": len(spans),
                "total_duration_ms": round(sum(durations), 2) if durations else 0,
                "avg_latency_ms": round(sum(durations) / len(durations), 2) if durations else 0,
                "min_latency_ms": round(min(durations), 2) if durations else 0,
                "max_latency_ms": round(max(durations), 2) if durations else 0,
                "p50_latency_ms": (round(sorted(durations)[len(durations) // 2], 2) if durations else 0),
                "p95_latency_ms": (round(sorted(durations)[int(len(durations) * 0.95)], 2) if len(durations) > 1 else (round(durations[0], 2) if durations else 0)),
                "total_tokens": total_tokens,
                "tokens_per_second": (round(total_tokens / total_duration_sec, 2) if total_duration_sec > 0 else 0),
            }

        return {
            "llm_megabeam_mistral_7b_300k": compute_stats(llm_only_spans),
            "vlm_qwen3_vl_30b_a3b_thinking": compute_stats(vlm_spans),
            "combined": compute_stats(llm_spans),
        }

    def _compute_tool_analytics(self) -> dict:
        """Compute tool execution metrics."""
        tool_spans = [s for s in self._spans if s["name"].startswith("tool.")]

        tool_stats = {}
        for span in tool_spans:
            name = span["name"].replace("tool.", "")
            if name not in tool_stats:
                tool_stats[name] = {"calls": 0, "total_ms": 0, "durations": []}
            tool_stats[name]["calls"] += 1
            if span.get("duration_ms"):
                tool_stats[name]["total_ms"] += span["duration_ms"]
                tool_stats[name]["durations"].append(span["duration_ms"])

        # Compute averages
        for name, stats in tool_stats.items():
            stats["avg_ms"] = round(stats["total_ms"] / stats["calls"], 2) if stats["calls"] > 0 else 0
            stats["total_ms"] = round(stats["total_ms"], 2)
            del stats["durations"]

        return tool_stats

    def _write_to_file(self):
        # Also update a "latest" file
        latest_path = self.output_dir / "traces_latest.json"
        llm_endpoint = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
        vlm_endpoint = os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1")

        # Compute analytics
        llm_analytics = self._compute_llm_analytics()
        tool_analytics = self._compute_tool_analytics()

        # Get agent span for total duration
        agent_spans = [s for s in self._spans if s["name"].startswith("agent.")]
        total_duration = agent_spans[-1]["duration_ms"] if agent_spans else 0

        output = {
            "service": OTEL_SERVICE_NAME,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "note": "Compare with/without KV cache offload by running same query",
                "llm_endpoint": f"{llm_endpoint} (MegaBeam-Mistral-7B-300k)",
                "vlm_endpoint": f"{vlm_endpoint} (Qwen3-VL-30B-A3B-Thinking)",
            },
            "summary": {
                "total_spans": len(self._spans),
                "total_duration_ms": round(total_duration, 2),
                "total_duration_sec": round(total_duration / 1000, 2) if total_duration else 0,
                "agents": len([s for s in self._spans if s["name"].startswith("agent.")]),
                "tools": len([s for s in self._spans if s["name"].startswith("tool.")]),
                "llm_calls": len([s for s in self._spans if "llm" in s["name"] or "vlm" in s["name"] or ("POST" in s["name"] and "chat/completions" in str(s.get("attributes", {})))]),
            },
            "llm_performance": llm_analytics,
            "tool_performance": tool_analytics,
            "spans": self._spans,
        }

        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

    def shutdown(self) -> None:
        """Flush accumulated telemetry to disk during exporter shutdown."""
        self._write_to_file()

    def force_flush(self, _timeout_millis: int = 30000) -> bool:
        """Force-flush buffered spans to disk."""
        self._write_to_file()
        return True


# Global state
_INITIALIZED = False
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None

# Metrics
_AGENT_INVOCATIONS = None
_AGENT_DURATION = None
_TOOL_CALLS = None
_TOOL_DURATION = None
_LLM_CALLS = None
_LLM_TOKENS = None
_ERRORS = None


def init_telemetry(  # pylint: disable=too-many-locals
    service_name: str = OTEL_SERVICE_NAME,
    otlp_endpoint: str = OTEL_ENDPOINT,
    console_export: bool = OTEL_CONSOLE_EXPORT,
    file_export: bool = OTEL_FILE_EXPORT,
) -> tuple[trace.Tracer, metrics.Meter]:
    """
    Initialize OpenTelemetry tracing and metrics.

    Args:
        service_name: Name of the service for telemetry
        otlp_endpoint: OTLP collector endpoint (e.g., Jaeger)
        console_export: If True, export to console (for debugging)
        file_export: If True, export to JSON files (default: True)

    Returns:
        Tuple of (Tracer, Meter)
    """
    if _INITIALIZED:
        return _tracer, _meter

    # Create resource
    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
        }
    )

    # Setup Tracing
    trace_provider = TracerProvider(resource=resource)

    # File export (default - always works)
    if file_export:
        file_exporter = FileSpanExporter(OTEL_OUTPUT_DIR)
        trace_provider.add_span_processor(BatchSpanProcessor(file_exporter))

    # OTLP export (optional - requires Jaeger/Zipkin)
    if OTLP_AVAILABLE and otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except (RuntimeError, OSError, ValueError, TypeError):
            pass  # Ignore if collector not available

    # Console export (optional - for debugging)
    if console_export:
        trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(__name__)

    # Setup Metrics
    readers = []
    if console_export:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=10000))

    if OTLP_AVAILABLE and otlp_endpoint:
        try:
            otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
            readers.append(PeriodicExportingMetricReader(otlp_metric_exporter))
        except (RuntimeError, OSError, ValueError, TypeError):
            pass

    if readers:
        meter_provider = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter(__name__)

    # Create metrics instruments
    agent_invocations = meter.create_counter("agent.invocations", description="Number of agent invocations", unit="1")
    agent_duration = meter.create_histogram("agent.duration", description="Agent execution duration", unit="s")
    tool_calls = meter.create_counter("agent.tool_calls", description="Number of tool calls", unit="1")
    tool_duration = meter.create_histogram("agent.tool_duration", description="Tool execution duration", unit="s")
    llm_calls = meter.create_counter("agent.llm_calls", description="Number of LLM/VLM API calls", unit="1")
    llm_tokens = meter.create_counter("agent.llm_tokens", description="Total tokens used", unit="1")
    errors = meter.create_counter("agent.errors", description="Number of errors", unit="1")

    # Auto-instrument HTTP calls (for LLM/VLM API tracking)
    HTTPXClientInstrumentor().instrument()

    globals().update(
        {
            "_tracer": tracer,
            "_meter": meter,
            "_AGENT_INVOCATIONS": agent_invocations,
            "_AGENT_DURATION": agent_duration,
            "_TOOL_CALLS": tool_calls,
            "_TOOL_DURATION": tool_duration,
            "_LLM_CALLS": llm_calls,
            "_LLM_TOKENS": llm_tokens,
            "_ERRORS": errors,
            "_INITIALIZED": True,
        }
    )
    return tracer, meter


def get_tracer() -> trace.Tracer:
    """Get the global tracer, initializing if needed."""
    if not _INITIALIZED:
        init_telemetry()
    return _tracer


def get_meter() -> metrics.Meter:
    """Get the global meter, initializing if needed."""
    if not _INITIALIZED:
        init_telemetry()
    return _meter


@contextmanager
def trace_agent(
    agent_name: str,
    video_path: str = "",
    query: str = "",
    analysis_type: str = "",
):
    """
    Context manager to trace an agent execution.

    Usage:
        with trace_agent("american_football_analytics", video_path="game.mp4", query="..."):
            result = agent.invoke(...)
    """
    tracer = get_tracer()
    start_time = time.time()

    with tracer.start_as_current_span(
        f"agent.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "agent.video_path": video_path,
            "agent.query": query[:200] if query else "",  # Truncate long queries
            "agent.analysis_type": analysis_type,
        },
    ) as span:
        try:
            if _AGENT_INVOCATIONS:
                _AGENT_INVOCATIONS.add(1, {"agent": agent_name, "type": analysis_type})

            yield span

            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            if _ERRORS:
                _ERRORS.add(1, {"agent": agent_name, "error_type": type(e).__name__})
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("agent.duration_seconds", duration)
            if _AGENT_DURATION:
                _AGENT_DURATION.record(duration, {"agent": agent_name})


@contextmanager
def trace_tool(tool_name: str, **attributes):
    """
    Context manager to trace a tool execution.

    Usage:
        with trace_tool("analyze_formation", frame_path="..."):
            result = analyze_play_formation(frame_path)
    """
    tracer = get_tracer()
    start_time = time.time()

    with tracer.start_as_current_span(
        f"tool.{tool_name}",
        attributes={
            "tool.name": tool_name,
            **{f"tool.{k}": str(v)[:100] for k, v in attributes.items()},
        },
    ) as span:
        try:
            if _TOOL_CALLS:
                _TOOL_CALLS.add(1, {"tool": tool_name})

            yield span

            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            if _ERRORS:
                _ERRORS.add(1, {"tool": tool_name, "error_type": type(e).__name__})
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("tool.duration_seconds", duration)
            if _TOOL_DURATION:
                _TOOL_DURATION.record(duration, {"tool": tool_name})


@contextmanager
def trace_llm_call(model: str, model_type: str = "llm"):
    """
    Context manager to trace LLM/VLM API calls.

    Usage:
        with trace_llm_call("megabeam-mistral-7b-300k", "llm") as span:
            response = client.post(...)
            span.set_attribute("llm.tokens", response.usage.total_tokens)
    """
    tracer = get_tracer()
    start_time = time.time()

    with tracer.start_as_current_span(f"{model_type}.call", attributes={"llm.model": model, "llm.type": model_type}) as span:
        try:
            if _LLM_CALLS:
                _LLM_CALLS.add(1, {"model": model, "type": model_type})

            yield span

            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("llm.duration_seconds", duration)


def record_tokens(tokens: int, model: str):
    """Record token usage."""
    if _LLM_TOKENS:
        _LLM_TOKENS.add(tokens, {"model": model})


def traced_tool(func: Callable) -> Callable:
    """
    Decorator to automatically trace tool functions.

    Usage:
        @traced_tool
        def analyze_play_formation(frame_path: str) -> dict:
            ...
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with trace_tool(func.__name__, args=str(args)[:100], kwargs=str(kwargs)[:100]):
            return func(*args, **kwargs)

    return wrapper


def traced_agent(agent_name: str):
    """
    Decorator factory to trace agent analysis functions.

    Usage:
        @traced_agent("american_football_analytics")
        def analyze_game_film(video_path, query, ...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            video_path = kwargs.get("video_path", args[0] if args else "")
            query = kwargs.get("query", args[1] if len(args) > 1 else "")
            analysis_type = kwargs.get("analysis_type", "")

            with trace_agent(agent_name, video_path, query, analysis_type):
                return func(*args, **kwargs)

        return wrapper

    return decorator
