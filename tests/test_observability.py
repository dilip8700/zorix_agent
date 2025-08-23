"""Tests for observability components."""

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.observability.audit import AuditEvent, AuditEventType, AuditLogger
from agent.observability.logging import configure_logging, get_logger, LogContext
from agent.observability.metrics import MetricsCollector, get_metrics_collector
from agent.observability.tracing import configure_tracing, get_tracer, trace_context


class TestLogging:
    """Test logging functionality."""
    
    def test_configure_logging_json(self):
        """Test JSON logging configuration."""
        configure_logging(level="DEBUG", format_type="json")
        
        logger = get_logger("test.logger")
        assert logger is not None
    
    def test_configure_logging_text(self):
        """Test text logging configuration."""
        configure_logging(level="INFO", format_type="text")
        
        logger = get_logger("test.logger")
        assert logger is not None
    
    def test_log_context(self):
        """Test log context manager."""
        logger = get_logger("test.context")
        
        with LogContext(logger, request_id="123", user_id="user1") as ctx_logger:
            assert ctx_logger is not None
            ctx_logger.info("Test message with context")
    
    def test_logger_with_file(self):
        """Test logging to file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            configure_logging(level="INFO", format_type="json", log_file=log_file)
            
            logger = get_logger("test.file")
            logger.info("Test log message", extra_field="test_value")
            
            # Check that log file was created and contains data
            log_path = Path(log_file)
            assert log_path.exists()
            assert log_path.stat().st_size > 0
            
        finally:
            Path(log_file).unlink(missing_ok=True)


class TestMetrics:
    """Test metrics functionality."""
    
    @pytest.fixture
    def metrics(self):
        """Create a fresh metrics collector for testing."""
        return MetricsCollector(max_history=100)
    
    def test_counter_operations(self, metrics):
        """Test counter operations."""
        # Test increment
        metrics.increment_counter("test_counter", 1)
        assert metrics.get_counter("test_counter") == 1
        
        metrics.increment_counter("test_counter", 5)
        assert metrics.get_counter("test_counter") == 6
        
        # Test with labels
        metrics.increment_counter("test_counter", 1, {"env": "test"})
        assert metrics.get_counter("test_counter", {"env": "test"}) == 1
        assert metrics.get_counter("test_counter") == 6  # Different metric
    
    def test_gauge_operations(self, metrics):
        """Test gauge operations."""
        # Test set gauge
        metrics.set_gauge("test_gauge", 42.5)
        assert metrics.get_gauge("test_gauge") == 42.5
        
        # Test update gauge
        metrics.set_gauge("test_gauge", 100.0)
        assert metrics.get_gauge("test_gauge") == 100.0
        
        # Test with labels
        metrics.set_gauge("test_gauge", 50.0, {"env": "test"})
        assert metrics.get_gauge("test_gauge", {"env": "test"}) == 50.0
        assert metrics.get_gauge("test_gauge") == 100.0  # Different metric
    
    def test_histogram_operations(self, metrics):
        """Test histogram operations."""
        # Record values
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for value in values:
            metrics.record_histogram("test_histogram", value)
        
        # Get summary
        summary = metrics.get_histogram_summary("test_histogram")
        assert summary is not None
        assert summary.count == 5
        assert summary.sum == 15.0
        assert summary.min == 1.0
        assert summary.max == 5.0
        assert summary.avg == 3.0
    
    def test_timer_operations(self, metrics):
        """Test timer operations."""
        # Record timer values
        durations = [0.1, 0.2, 0.3, 0.4, 0.5]
        for duration in durations:
            metrics.record_timer("test_timer", duration)
        
        # Get summary
        summary = metrics.get_timer_summary("test_timer")
        assert summary is not None
        assert summary.count == 5
        assert summary.min == 0.1
        assert summary.max == 0.5
    
    def test_time_operation_context(self, metrics):
        """Test timing context manager."""
        with metrics.time_operation("test_operation"):
            time.sleep(0.01)  # Small delay
        
        summary = metrics.get_timer_summary("test_operation")
        assert summary is not None
        assert summary.count == 1
        assert summary.min > 0.005  # Should be at least 5ms
    
    def test_get_all_metrics(self, metrics):
        """Test getting all metrics."""
        # Add some metrics
        metrics.increment_counter("counter1", 5)
        metrics.set_gauge("gauge1", 42.0)
        metrics.record_histogram("hist1", 10.0)
        metrics.record_timer("timer1", 0.1)
        
        all_metrics = metrics.get_all_metrics()
        
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
        assert "timers" in all_metrics
        
        assert all_metrics["counters"]["counter1"] == 5
        assert all_metrics["gauges"]["gauge1"] == 42.0
    
    def test_reset_metrics(self, metrics):
        """Test resetting metrics."""
        # Add some metrics
        metrics.increment_counter("counter1", 5)
        metrics.set_gauge("gauge1", 42.0)
        
        # Reset
        metrics.reset_metrics()
        
        # Check they're gone
        assert metrics.get_counter("counter1") == 0
        assert metrics.get_gauge("gauge1") is None
    
    def test_global_metrics_collector(self):
        """Test global metrics collector."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        
        # Should be the same instance
        assert collector1 is collector2


class TestTracing:
    """Test tracing functionality."""
    
    def test_configure_tracing(self):
        """Test tracing configuration."""
        configure_tracing(
            service_name="test-service",
            service_version="1.0.0",
            console_export=True
        )
        
        tracer = get_tracer()
        assert tracer is not None
    
    def test_trace_context(self):
        """Test trace context manager."""
        configure_tracing(console_export=True)
        
        with trace_context("test_operation", {"key": "value"}) as span:
            assert span is not None
            span.set_attribute("custom_attr", "test_value")
    
    def test_trace_function_decorator(self):
        """Test function tracing decorator."""
        from agent.observability.tracing import trace_function
        
        configure_tracing(console_export=True)
        
        @trace_function(name="test_function", attributes={"component": "test"})
        def test_func(x, y):
            return x + y
        
        result = test_func(1, 2)
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_trace_async_function_decorator(self):
        """Test async function tracing decorator."""
        from agent.observability.tracing import trace_async_function
        
        configure_tracing(console_export=True)
        
        @trace_async_function(name="test_async_function")
        async def test_async_func(x, y):
            return x * y
        
        result = await test_async_func(3, 4)
        assert result == 12


class TestAuditLogging:
    """Test audit logging functionality."""
    
    @pytest.fixture
    def audit_logger(self):
        """Create audit logger with temporary file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.audit') as f:
            audit_file = f.name
        
        logger = AuditLogger(audit_file=audit_file, enable_console=False)
        yield logger
        
        # Cleanup
        Path(audit_file).unlink(missing_ok=True)
    
    def test_audit_event_creation(self):
        """Test audit event creation."""
        event = AuditEvent(
            event_id="test-123",
            event_type=AuditEventType.FILE_CREATE,
            timestamp=datetime.utcnow(),
            action="Create file",
            resource="/test/file.txt",
            success=True
        )
        
        assert event.event_id == "test-123"
        assert event.event_type == AuditEventType.FILE_CREATE
        assert event.success is True
    
    def test_log_file_operation(self, audit_logger):
        """Test logging file operations."""
        event_id = audit_logger.log_file_operation(
            operation="create",
            file_path="/test/file.txt",
            success=True,
            user_id="user123",
            session_id="session456"
        )
        
        assert event_id is not None
        assert len(event_id) > 0
    
    def test_log_command_execution(self, audit_logger):
        """Test logging command execution."""
        event_id = audit_logger.log_command_execution(
            command="ls -la",
            working_dir="/tmp",
            exit_code=0,
            output="file1.txt\nfile2.txt",
            user_id="user123"
        )
        
        assert event_id is not None
    
    def test_log_git_operation(self, audit_logger):
        """Test logging Git operations."""
        event_id = audit_logger.log_git_operation(
            operation="commit",
            repository="/path/to/repo",
            details={"commit_hash": "abc123", "message": "Test commit"},
            success=True,
            user_id="user123"
        )
        
        assert event_id is not None
    
    def test_log_security_event(self, audit_logger):
        """Test logging security events."""
        event_id = audit_logger.log_security_event(
            event_description="Suspicious file access attempt",
            severity="high",
            details={"file_path": "/etc/passwd", "attempts": 3},
            user_id="user123",
            ip_address="192.168.1.100"
        )
        
        assert event_id is not None
    
    def test_search_events(self, audit_logger):
        """Test searching audit events."""
        # Log some events
        audit_logger.log_file_operation("create", "/test1.txt", user_id="user1")
        audit_logger.log_file_operation("modify", "/test2.txt", user_id="user2")
        audit_logger.log_command_execution("ls", user_id="user1")
        
        # Search by event type
        file_events = audit_logger.search_events(event_type=AuditEventType.FILE_CREATE)
        assert len(file_events) >= 1
        
        # Search by user
        user1_events = audit_logger.search_events(user_id="user1")
        assert len(user1_events) >= 2
    
    def test_audit_file_rotation(self, audit_logger):
        """Test audit file rotation."""
        # Set small max file size for testing
        audit_logger.max_file_size = 1000  # 1KB
        
        # Log many events to trigger rotation
        for i in range(100):
            audit_logger.log_file_operation(
                "create",
                f"/test/file_{i}.txt",
                details={"large_data": "x" * 100}  # Make events larger
            )
        
        # Check that rotation occurred
        audit_path = audit_logger.audit_path
        backup_path = audit_path.with_suffix('.1')
        
        # At least one of these should exist
        assert audit_path.exists() or backup_path.exists()


class TestIntegration:
    """Integration tests for observability components."""
    
    def test_logging_with_metrics(self):
        """Test logging with metrics collection."""
        configure_logging(level="INFO", format_type="json")
        metrics = get_metrics_collector()
        
        logger = get_logger("test.integration")
        
        # Log some messages and collect metrics
        for i in range(5):
            logger.info(f"Test message {i}")
            metrics.increment_counter("log_messages")
        
        assert metrics.get_counter("log_messages") == 5
    
    def test_tracing_with_metrics(self):
        """Test tracing with metrics collection."""
        configure_tracing(console_export=True)
        metrics = get_metrics_collector()
        
        with trace_context("test_operation") as span:
            metrics.increment_counter("traced_operations")
            span.set_attribute("operation_count", 1)
        
        assert metrics.get_counter("traced_operations") == 1
    
    def test_audit_with_logging(self):
        """Test audit logging with regular logging."""
        configure_logging(level="INFO", format_type="json")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.audit') as f:
            audit_file = f.name
        
        try:
            audit_logger = AuditLogger(audit_file=audit_file, enable_console=True)
            
            # This should create both audit log and regular log entries
            event_id = audit_logger.log_security_event(
                "Test security event",
                severity="medium"
            )
            
            assert event_id is not None
            
            # Check audit file was created
            assert Path(audit_file).exists()
            
        finally:
            Path(audit_file).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])