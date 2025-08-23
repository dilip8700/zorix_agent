"""OpenTelemetry tracing configuration for Zorix Agent."""

import functools
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from agent.config import get_settings
from agent.observability.logging import get_logger

logger = get_logger(__name__)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None


def configure_tracing(
    service_name: str = "zorix-agent",
    service_version: str = "1.0.0",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
    enable_auto_instrumentation: bool = True
) -> None:
    """Configure OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OTLP endpoint for trace export
        console_export: Whether to export traces to console
        enable_auto_instrumentation: Whether to enable auto-instrumentation
    """
    global _tracer
    
    settings = get_settings()
    
    # Create resource
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "service.instance.id": f"{service_name}-{int(time.time())}",
        "deployment.environment": getattr(settings, "environment", "development"),
    })
    
    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # Configure exporters
    processors = []
    
    # OTLP exporter
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            processors.append(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP trace exporter configured", endpoint=otlp_endpoint)
        except Exception as e:
            logger.warning("Failed to configure OTLP exporter", error=str(e))
    
    # Console exporter for development
    if console_export:
        console_exporter = ConsoleSpanExporter()
        processors.append(BatchSpanProcessor(console_exporter))
        logger.info("Console trace exporter configured")
    
    # Add processors to tracer provider
    for processor in processors:
        tracer_provider.add_span_processor(processor)
    
    # Get tracer
    _tracer = trace.get_tracer(service_name, service_version)
    
    # Enable auto-instrumentation
    if enable_auto_instrumentation:
        try:
            RequestsInstrumentor().instrument()
            URLLib3Instrumentor().instrument()
            # Boto3SQSInstrumentor().instrument()  # Uncomment if using SQS
            # SQLAlchemyInstrumentor().instrument()  # Uncomment if using SQLAlchemy
            logger.info("Auto-instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to enable auto-instrumentation", error=str(e))
    
    logger.info("Tracing configured successfully")


def get_tracer() -> trace.Tracer:
    """Get the configured tracer instance.
    
    Returns:
        OpenTelemetry tracer
    """
    global _tracer
    
    if _tracer is None:
        # Configure with defaults if not already configured
        configure_tracing()
    
    return _tracer


def trace_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """Decorator to trace function execution.
    
    Args:
        name: Custom span name (defaults to function name)
        attributes: Additional attributes to add to the span
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                # Add argument information (be careful with sensitive data)
                if args:
                    span.set_attribute("function.args.count", len(args))
                if kwargs:
                    span.set_attribute("function.kwargs.count", len(kwargs))
                    # Add non-sensitive kwargs
                    safe_kwargs = {
                        k: str(v)[:100] for k, v in kwargs.items()
                        if not any(sensitive in k.lower() for sensitive in [
                            "password", "token", "key", "secret", "auth"
                        ])
                    }
                    for key, value in safe_kwargs.items():
                        span.set_attribute(f"function.kwargs.{key}", value)
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    
                    # Record success
                    span.set_attribute("function.success", True)
                    span.set_attribute("function.duration_ms", (time.time() - start_time) * 1000)
                    
                    if result is not None:
                        span.set_attribute("function.result.type", type(result).__name__)
                        if hasattr(result, "__len__"):
                            try:
                                span.set_attribute("function.result.length", len(result))
                            except:
                                pass
                    
                    return result
                    
                except Exception as e:
                    # Record error
                    span.set_attribute("function.success", False)
                    span.set_attribute("function.error.type", type(e).__name__)
                    span.set_attribute("function.error.message", str(e))
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def trace_async_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """Decorator to trace async function execution.
    
    Args:
        name: Custom span name (defaults to function name)
        attributes: Additional attributes to add to the span
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("function.async", True)
                
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                # Add argument information
                if args:
                    span.set_attribute("function.args.count", len(args))
                if kwargs:
                    span.set_attribute("function.kwargs.count", len(kwargs))
                
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    
                    # Record success
                    span.set_attribute("function.success", True)
                    span.set_attribute("function.duration_ms", (time.time() - start_time) * 1000)
                    
                    if result is not None:
                        span.set_attribute("function.result.type", type(result).__name__)
                    
                    return result
                    
                except Exception as e:
                    # Record error
                    span.set_attribute("function.success", False)
                    span.set_attribute("function.error.type", type(e).__name__)
                    span.set_attribute("function.error.message", str(e))
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


@contextmanager
def trace_context(
    name: str,
    attributes: Optional[Dict[str, Any]] = None
):
    """Context manager for tracing code blocks.
    
    Args:
        name: Span name
        attributes: Additional attributes to add to the span
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        
        try:
            yield span
        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


class TracingMixin:
    """Mixin class to add tracing capabilities to any class."""
    
    def trace_method(self, method_name: str, **attributes):
        """Create a span for a method call."""
        tracer = get_tracer()
        span_name = f"{self.__class__.__name__}.{method_name}"
        
        return tracer.start_as_current_span(
            span_name,
            attributes={
                "class.name": self.__class__.__name__,
                "class.module": self.__class__.__module__,
                **attributes
            }
        )


def add_span_attributes(**attributes):
    """Add attributes to the current span."""
    current_span = trace.get_current_span()
    if current_span.is_recording():
        for key, value in attributes.items():
            current_span.set_attribute(key, str(value))


def record_exception(exception: Exception):
    """Record an exception in the current span."""
    current_span = trace.get_current_span()
    if current_span.is_recording():
        current_span.record_exception(exception)
        current_span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


def create_child_span(name: str, **attributes):
    """Create a child span of the current span."""
    tracer = get_tracer()
    return tracer.start_as_current_span(name, attributes=attributes)