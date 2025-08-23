#!/usr/bin/env python3
"""
Integration tests for observability system.

This script tests the complete observability stack with real components.
"""

import asyncio
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.observability import (
    configure_logging,
    configure_tracing,
    get_audit_logger,
    get_logger,
    get_metrics_collector,
    get_tracer,
)
from agent.observability.audit import AuditEventType
from agent.observability.logging import LogContext, log_async_function_call, log_function_call
from agent.observability.metrics import time_operation
from agent.observability.tracing import trace_context, trace_function, trace_async_function


def test_logging_configuration():
    """Test logging configuration and usage."""
    print("Testing logging configuration...")
    
    # Configure structured logging
    configure_logging(
        level="INFO",
        format_type="json",
        context={"test_run": "observability_integration"}
    )
    
    logger = get_logger("test.logging")
    
    # Test basic logging
    logger.info("Basic log message", component="test")
    logger.warning("Warning message", alert_level="medium")
    logger.error("Error message", error_code="TEST001")
    
    # Test log context
    with LogContext(logger, request_id="req-123", user_id="user-456") as ctx_logger:
        ctx_logger.info("Message with context")
        ctx_logger.debug("Debug message with context", debug_info="test_data")
    
    print("✓ Logging configuration test passed")


def test_metrics_collection():
    """Test metrics collection and reporting."""
    print("Testing metrics collection...")
    
    metrics = get_metrics_collector()
    
    # Test counters
    for i in range(10):
        metrics.increment_counter("test_requests", 1, {"endpoint": "/api/test"})
        metrics.increment_counter("test_requests", 1, {"endpoint": "/api/health"})
    
    # Test gauges
    metrics.set_gauge("active_connections", 25.0)
    metrics.set_gauge("memory_usage_mb", 512.5, {"process": "main"})
    
    # Test histograms
    response_times = [0.1, 0.2, 0.15, 0.3, 0.25, 0.18, 0.22, 0.35, 0.12, 0.28]
    for rt in response_times:
        metrics.record_histogram("response_time", rt, {"endpoint": "/api/test"})
    
    # Test timers with context manager
    with time_operation("database_query", {"table": "users"}):
        time.sleep(0.05)  # Simulate database operation
    
    with time_operation("cache_lookup", {"cache": "redis"}):
        time.sleep(0.01)  # Simulate cache lookup
    
    # Get and display metrics
    all_metrics = metrics.get_all_metrics()
    
    print(f"Counters: {len(all_metrics['counters'])}")
    print(f"Gauges: {len(all_metrics['gauges'])}")
    print(f"Histograms: {len(all_metrics['histograms'])}")
    print(f"Timers: {len(all_metrics['timers'])}")
    
    # Test specific metrics
    test_counter = metrics.get_counter("test_requests", {"endpoint": "/api/test"})
    assert test_counter == 10, f"Expected 10, got {test_counter}"
    
    response_time_summary = metrics.get_histogram_summary("response_time", {"endpoint": "/api/test"})
    assert response_time_summary is not None
    assert response_time_summary.count == 10
    
    print("✓ Metrics collection test passed")


def test_tracing_system():
    """Test OpenTelemetry tracing."""
    print("Testing tracing system...")
    
    # Configure tracing with console export for testing
    configure_tracing(
        service_name="zorix-agent-test",
        service_version="1.0.0",
        console_export=True,
        enable_auto_instrumentation=False  # Disable for testing
    )
    
    tracer = get_tracer()
    
    # Test manual span creation
    with tracer.start_as_current_span("test_operation") as span:
        span.set_attribute("operation.type", "test")
        span.set_attribute("operation.id", "test-123")
        
        # Nested span
        with tracer.start_as_current_span("nested_operation") as nested_span:
            nested_span.set_attribute("nested.value", "test_data")
            time.sleep(0.01)
    
    # Test trace context manager
    with trace_context("context_operation", {"context_id": "ctx-456"}) as span:
        span.set_attribute("custom_attribute", "test_value")
        time.sleep(0.01)
    
    print("✓ Tracing system test passed")


def test_function_decorators():
    """Test function tracing and logging decorators."""
    print("Testing function decorators...")
    
    @trace_function(name="test_sync_function", attributes={"function_type": "sync"})
    @log_function_call
    def sync_test_function(x: int, y: int) -> int:
        """Test synchronous function."""
        time.sleep(0.01)
        return x + y
    
    @trace_async_function(name="test_async_function", attributes={"function_type": "async"})
    @log_async_function_call
    async def async_test_function(x: int, y: int) -> int:
        """Test asynchronous function."""
        await asyncio.sleep(0.01)
        return x * y
    
    # Test sync function
    result1 = sync_test_function(5, 3)
    assert result1 == 8
    
    # Test async function
    async def run_async_test():
        result2 = await async_test_function(4, 6)
        assert result2 == 24
        return result2
    
    asyncio.run(run_async_test())
    
    print("✓ Function decorators test passed")


def test_audit_logging():
    """Test audit logging functionality."""
    print("Testing audit logging...")
    
    # Create temporary audit file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.audit') as f:
        audit_file = f.name
    
    try:
        # Configure audit logger
        from agent.observability.audit import AuditLogger
        audit_logger = AuditLogger(audit_file=audit_file, enable_console=True)
        
        # Test various audit events
        
        # File operations
        file_event_id = audit_logger.log_file_operation(
            operation="create",
            file_path="/test/example.py",
            success=True,
            details={"file_size": 1024, "encoding": "utf-8"},
            user_id="test_user",
            session_id="session_123"
        )
        
        audit_logger.log_file_operation(
            operation="modify",
            file_path="/test/example.py",
            success=True,
            details={"changes": "Added function", "lines_added": 10},
            user_id="test_user",
            session_id="session_123"
        )
        
        # Command execution
        cmd_event_id = audit_logger.log_command_execution(
            command="python test.py",
            working_dir="/test",
            exit_code=0,
            output="Test completed successfully",
            user_id="test_user",
            session_id="session_123"
        )
        
        # Git operations
        git_event_id = audit_logger.log_git_operation(
            operation="commit",
            repository="/test/repo",
            details={
                "commit_hash": "abc123def456",
                "message": "Add new feature",
                "files_changed": 3
            },
            success=True,
            user_id="test_user",
            session_id="session_123"
        )
        
        # Security events
        security_event_id = audit_logger.log_security_event(
            event_description="Attempted access to restricted file",
            severity="medium",
            details={
                "file_path": "/etc/sensitive.conf",
                "access_type": "read",
                "blocked": True
            },
            user_id="test_user",
            ip_address="192.168.1.100"
        )
        
        # Task events
        task_event_id = audit_logger.log_task_event(
            task_id="task_789",
            event_type=AuditEventType.TASK_START,
            task_description="Process data files",
            details={"input_files": 5, "expected_duration": "10 minutes"},
            user_id="test_user",
            session_id="session_123"
        )
        
        print(f"Logged events: {file_event_id}, {cmd_event_id}, {git_event_id}, {security_event_id}, {task_event_id}")
        
        # Test event search
        all_events = audit_logger.search_events(limit=10)
        print(f"Found {len(all_events)} audit events")
        
        user_events = audit_logger.search_events(user_id="test_user", limit=10)
        print(f"Found {len(user_events)} events for test_user")
        
        file_events = audit_logger.search_events(event_type=AuditEventType.FILE_CREATE, limit=10)
        print(f"Found {len(file_events)} file creation events")
        
        # Verify audit file exists and has content
        audit_path = Path(audit_file)
        assert audit_path.exists()
        assert audit_path.stat().st_size > 0
        
        print("✓ Audit logging test passed")
        
    finally:
        # Cleanup
        Path(audit_file).unlink(missing_ok=True)


def test_error_handling():
    """Test error handling in observability components."""
    print("Testing error handling...")
    
    logger = get_logger("test.errors")
    metrics = get_metrics_collector()
    tracer = get_tracer()
    
    # Test logging with exception
    try:
        raise ValueError("Test exception for logging")
    except Exception as e:
        logger.error("Caught test exception", exc_info=True, error_type=type(e).__name__)
        metrics.increment_counter("errors", 1, {"error_type": "ValueError"})
    
    # Test tracing with exception
    try:
        with trace_context("error_operation") as span:
            span.set_attribute("operation.will_fail", True)
            raise RuntimeError("Test exception for tracing")
    except Exception as e:
        logger.info("Exception properly recorded in trace")
    
    # Test metrics with error conditions
    with metrics.time_operation("failing_operation", {"expected_failure": "true"}):
        try:
            time.sleep(0.01)
            raise ConnectionError("Simulated connection failure")
        except Exception:
            metrics.increment_counter("operation_failures", 1, {"operation": "failing_operation"})
    
    print("✓ Error handling test passed")


def test_performance_impact():
    """Test performance impact of observability."""
    print("Testing performance impact...")
    
    # Baseline - no observability
    start_time = time.time()
    for i in range(1000):
        result = i * 2 + 1
    baseline_time = time.time() - start_time
    
    # With observability
    logger = get_logger("test.performance")
    metrics = get_metrics_collector()
    
    start_time = time.time()
    for i in range(1000):
        if i % 100 == 0:  # Log every 100th iteration
            logger.debug("Performance test iteration", iteration=i)
        
        if i % 50 == 0:  # Metrics every 50th iteration
            metrics.increment_counter("performance_iterations")
            metrics.record_histogram("iteration_value", float(i))
        
        result = i * 2 + 1
    
    observability_time = time.time() - start_time
    
    overhead_percent = ((observability_time - baseline_time) / baseline_time) * 100
    
    print(f"Baseline time: {baseline_time:.4f}s")
    print(f"With observability: {observability_time:.4f}s")
    print(f"Overhead: {overhead_percent:.2f}%")
    
    # Overhead should be reasonable (less than 50% for this test)
    assert overhead_percent < 50, f"Observability overhead too high: {overhead_percent:.2f}%"
    
    print("✓ Performance impact test passed")


async def test_async_observability():
    """Test observability with async operations."""
    print("Testing async observability...")
    
    logger = get_logger("test.async")
    metrics = get_metrics_collector()
    
    async def async_operation(operation_id: int):
        """Simulate async operation with observability."""
        with trace_context(f"async_op_{operation_id}") as span:
            span.set_attribute("operation.id", operation_id)
            
            logger.info("Starting async operation", operation_id=operation_id)
            
            with metrics.time_operation("async_operation", {"operation_id": str(operation_id)}):
                await asyncio.sleep(0.01)  # Simulate async work
                
                if operation_id % 10 == 0:
                    metrics.increment_counter("async_milestones", 1)
            
            logger.info("Completed async operation", operation_id=operation_id)
            return operation_id * 2
    
    # Run multiple async operations concurrently
    tasks = [async_operation(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 20
    assert all(results[i] == i * 2 for i in range(20))
    
    # Check metrics
    milestone_count = metrics.get_counter("async_milestones")
    assert milestone_count == 2  # operations 0 and 10
    
    print("✓ Async observability test passed")


async def main():
    """Run all observability integration tests."""
    print("Starting observability integration tests...\n")
    
    try:
        test_logging_configuration()
        print()
        
        test_metrics_collection()
        print()
        
        test_tracing_system()
        print()
        
        test_function_decorators()
        print()
        
        test_audit_logging()
        print()
        
        test_error_handling()
        print()
        
        test_performance_impact()
        print()
        
        await test_async_observability()
        print()
        
        print("🎉 All observability integration tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)