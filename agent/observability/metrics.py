"""Metrics collection for Zorix Agent."""

import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Union

from agent.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: Union[int, float]
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p95: float
    p99: float


class MetricsCollector:
    """Collects and manages application metrics."""
    
    def __init__(self, max_history: int = 10000):
        """Initialize metrics collector.
        
        Args:
            max_history: Maximum number of metric values to keep in memory
        """
        self.max_history = max_history
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._lock = Lock()
        
        logger.info("Metrics collector initialized", max_history=max_history)
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric.
        
        Args:
            name: Counter name
            value: Value to increment by
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value
            
            logger.debug(
                "Counter incremented",
                counter=name,
                value=value,
                total=self._counters[key],
                labels=labels
            )
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value.
        
        Args:
            name: Gauge name
            value: Gauge value
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            
            logger.debug(
                "Gauge set",
                gauge=name,
                value=value,
                labels=labels
            )
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a value in a histogram.
        
        Args:
            name: Histogram name
            value: Value to record
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(MetricValue(
                value=value,
                timestamp=time.time(),
                labels=labels or {}
            ))
            
            logger.debug(
                "Histogram value recorded",
                histogram=name,
                value=value,
                labels=labels
            )
    
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer duration.
        
        Args:
            name: Timer name
            duration: Duration in seconds
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._timers[key].append(MetricValue(
                value=duration,
                timestamp=time.time(),
                labels=labels or {}
            ))
            
            logger.debug(
                "Timer recorded",
                timer=name,
                duration=duration,
                labels=labels
            )
    
    @contextmanager
    def time_operation(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager to time an operation.
        
        Args:
            name: Timer name
            labels: Optional labels for the metric
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timer(name, duration, labels)
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get counter value.
        
        Args:
            name: Counter name
            labels: Optional labels for the metric
            
        Returns:
            Counter value
        """
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value.
        
        Args:
            name: Gauge name
            labels: Optional labels for the metric
            
        Returns:
            Gauge value or None if not set
        """
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key)
    
    def get_histogram_summary(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[MetricSummary]:
        """Get histogram summary statistics.
        
        Args:
            name: Histogram name
            labels: Optional labels for the metric
            
        Returns:
            Histogram summary or None if no data
        """
        with self._lock:
            key = self._make_key(name, labels)
            values = self._histograms.get(key)
            
            if not values:
                return None
            
            return self._calculate_summary([v.value for v in values])
    
    def get_timer_summary(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[MetricSummary]:
        """Get timer summary statistics.
        
        Args:
            name: Timer name
            labels: Optional labels for the metric
            
        Returns:
            Timer summary or None if no data
        """
        with self._lock:
            key = self._make_key(name, labels)
            values = self._timers.get(key)
            
            if not values:
                return None
            
            return self._calculate_summary([v.value for v in values])
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary.
        
        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "timers": {}
            }
            
            # Add histogram summaries
            for key, values in self._histograms.items():
                if values:
                    metrics["histograms"][key] = self._calculate_summary([v.value for v in values])
            
            # Add timer summaries
            for key, values in self._timers.items():
                if values:
                    metrics["timers"][key] = self._calculate_summary([v.value for v in values])
            
            return metrics
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            
            logger.info("All metrics reset")
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a key for the metric with labels.
        
        Args:
            name: Metric name
            labels: Optional labels
            
        Returns:
            Metric key
        """
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _calculate_summary(self, values: List[float]) -> MetricSummary:
        """Calculate summary statistics for a list of values.
        
        Args:
            values: List of values
            
        Returns:
            Summary statistics
        """
        if not values:
            return MetricSummary(0, 0, 0, 0, 0, 0, 0, 0)
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        total = sum(sorted_values)
        
        return MetricSummary(
            count=count,
            sum=total,
            min=sorted_values[0],
            max=sorted_values[-1],
            avg=total / count,
            p50=self._percentile(sorted_values, 0.5),
            p95=self._percentile(sorted_values, 0.95),
            p99=self._percentile(sorted_values, 0.99)
        )
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values.
        
        Args:
            sorted_values: Sorted list of values
            percentile: Percentile to calculate (0.0 to 1.0)
            
        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0.0
        
        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    
    return _metrics_collector


# Convenience functions for common metrics
def increment_counter(name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
    """Increment a counter metric."""
    get_metrics_collector().increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Set a gauge metric."""
    get_metrics_collector().set_gauge(name, value, labels)


def record_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record a histogram value."""
    get_metrics_collector().record_histogram(name, value, labels)


def record_timer(name: str, duration: float, labels: Optional[Dict[str, str]] = None):
    """Record a timer duration."""
    get_metrics_collector().record_timer(name, duration, labels)


def time_operation(name: str, labels: Optional[Dict[str, str]] = None):
    """Time an operation."""
    return get_metrics_collector().time_operation(name, labels)


class MetricsMixin:
    """Mixin class to add metrics capabilities to any class."""
    
    @property
    def metrics(self) -> MetricsCollector:
        """Get metrics collector."""
        return get_metrics_collector()
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter with class context."""
        class_labels = {"class": self.__class__.__name__}
        if labels:
            class_labels.update(labels)
        self.metrics.increment_counter(name, value, class_labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge with class context."""
        class_labels = {"class": self.__class__.__name__}
        if labels:
            class_labels.update(labels)
        self.metrics.set_gauge(name, value, class_labels)
    
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer with class context."""
        class_labels = {"class": self.__class__.__name__}
        if labels:
            class_labels.update(labels)
        self.metrics.record_timer(name, duration, class_labels)
    
    def time_method(self, method_name: str, labels: Optional[Dict[str, str]] = None):
        """Time a method execution."""
        class_labels = {"class": self.__class__.__name__, "method": method_name}
        if labels:
            class_labels.update(labels)
        return self.metrics.time_operation(f"method_duration", class_labels)