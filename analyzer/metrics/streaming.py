"""
Streaming metrics aggregator for JMeter test results.

This module provides single-pass, bounded-memory aggregation of JMeter
samples. It produces results numerically identical to MetricsCalculator
(including exact percentiles via a response-time histogram), except that
time-series buckets are aligned to absolute epoch multiples of the
interval rather than to the first sample's timestamp.
"""

import math
from collections import Counter
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from analyzer.models import EndpointMetrics, OverallMetrics, Sample, TimeSeriesMetrics


def percentile_from_histogram(hist: Counter, total: int, percentile: float) -> float:
    """Compute a percentile from a value->count histogram.

    Replicates MetricsCalculator._calculate_percentile exactly:
    index = (percentile / 100) * (total - 1); integer index returns the
    value at that rank, otherwise linear interpolation between the values
    at the floor and ceil ranks.

    Args:
        hist: Counter mapping response-time values to occurrences
        total: Total number of samples represented by the histogram
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value
    """
    if total <= 0 or not hist:
        return 0

    def value_at_rank(rank: int) -> float:
        cumulative = 0
        for value in sorted(hist):
            cumulative += hist[value]
            if cumulative > rank:
                return value
        return sorted(hist)[-1]

    index = (percentile / 100) * (total - 1)

    if index == int(index):
        return float(value_at_rank(int(index)))

    lower_index = math.floor(index)
    upper_index = math.ceil(index)
    lower_value = value_at_rank(lower_index)
    upper_value = value_at_rank(upper_index)
    fraction = index - lower_index

    return lower_value + (upper_value - lower_value) * fraction


class _Accumulator:
    """Running statistics for a scope (overall or per-endpoint).

    Keeps a response-time histogram instead of a sample list, so memory
    is bounded by the number of distinct response times.
    """

    def __init__(self) -> None:
        self.count = 0
        self.error_count = 0
        self.rt_sum = 0
        self.rt_min: Optional[int] = None
        self.rt_max: Optional[int] = None
        self.rt_histogram: Counter = Counter()
        self.first_ts: Optional[datetime] = None
        self.last_ts: Optional[datetime] = None

    def add(self, sample: Sample) -> None:
        self.count += 1
        if not sample.success:
            self.error_count += 1
        rt = sample.response_time
        self.rt_sum += rt
        self.rt_histogram[rt] += 1
        if self.rt_min is None or rt < self.rt_min:
            self.rt_min = rt
        if self.rt_max is None or rt > self.rt_max:
            self.rt_max = rt
        if self.first_ts is None or sample.timestamp < self.first_ts:
            self.first_ts = sample.timestamp
        if self.last_ts is None or sample.timestamp > self.last_ts:
            self.last_ts = sample.timestamp

    def to_metrics(self) -> OverallMetrics:
        if self.first_ts is not None and self.last_ts is not None:
            duration = (self.last_ts - self.first_ts).total_seconds()
        else:
            duration = 0
        throughput = self.count / duration if duration > 0 else 0
        return OverallMetrics(
            total_samples=self.count,
            error_count=self.error_count,
            error_rate=(self.error_count / self.count) * 100 if self.count else 0,
            average_response_time=self.rt_sum / self.count if self.count else 0,
            median_response_time=percentile_from_histogram(self.rt_histogram, self.count, 50),
            percentile_90=percentile_from_histogram(self.rt_histogram, self.count, 90),
            percentile_95=percentile_from_histogram(self.rt_histogram, self.count, 95),
            percentile_99=percentile_from_histogram(self.rt_histogram, self.count, 99),
            min_response_time=self.rt_min if self.rt_min is not None else 0,
            max_response_time=self.rt_max if self.rt_max is not None else 0,
            throughput=throughput,
            test_duration=duration
        )


class _IntervalBucket:
    """Per-interval running stats (no sample list)."""

    __slots__ = ("count", "error_count", "rt_sum", "threads")

    def __init__(self) -> None:
        self.count = 0
        self.error_count = 0
        self.rt_sum = 0
        self.threads = set()

    def add(self, sample: Sample) -> None:
        self.count += 1
        if not sample.success:
            self.error_count += 1
        self.rt_sum += sample.response_time
        if sample.thread_name:
            self.threads.add(sample.thread_name)


class StreamingAggregator:
    """Single-pass streaming aggregator over JMeter samples."""

    def __init__(self, interval_seconds: int = 5) -> None:
        self.interval_seconds = interval_seconds
        self._overall = _Accumulator()
        self._endpoints: Dict[str, _Accumulator] = {}
        self._intervals: Dict[int, _IntervalBucket] = {}
        self._error_types: Counter = Counter()
        self._error_intervals: Counter = Counter()

    def add(self, sample: Sample) -> None:
        self._overall.add(sample)

        endpoint_acc = self._endpoints.get(sample.label)
        if endpoint_acc is None:
            endpoint_acc = self._endpoints[sample.label] = _Accumulator()
        endpoint_acc.add(sample)

        bucket_key = int(sample.timestamp.timestamp() // self.interval_seconds)
        bucket = self._intervals.get(bucket_key)
        if bucket is None:
            bucket = self._intervals[bucket_key] = _IntervalBucket()
        bucket.add(sample)

        if not sample.success:
            self._error_types[sample.error_message or f"HTTP {sample.response_code}"] += 1
            self._error_intervals[bucket_key] += 1

    def consume(self, samples: Iterable[Sample]) -> "StreamingAggregator":
        for sample in samples:
            self.add(sample)
        return self

    @property
    def start_time(self) -> Optional[datetime]:
        return self._overall.first_ts

    @property
    def end_time(self) -> Optional[datetime]:
        return self._overall.last_ts

    def overall_metrics(self) -> OverallMetrics:
        if self._overall.count == 0:
            raise ValueError("Cannot calculate metrics for empty test results")
        return self._overall.to_metrics()

    def endpoint_metrics(self) -> Dict[str, EndpointMetrics]:
        if self._overall.count == 0:
            raise ValueError("Cannot calculate metrics for empty test results")
        result = {}
        for endpoint, acc in self._endpoints.items():
            metrics = acc.to_metrics()
            result[endpoint] = EndpointMetrics(
                endpoint=endpoint,
                total_samples=metrics.total_samples,
                error_count=metrics.error_count,
                error_rate=metrics.error_rate,
                average_response_time=metrics.average_response_time,
                median_response_time=metrics.median_response_time,
                percentile_90=metrics.percentile_90,
                percentile_95=metrics.percentile_95,
                percentile_99=metrics.percentile_99,
                min_response_time=metrics.min_response_time,
                max_response_time=metrics.max_response_time,
                throughput=metrics.throughput,
                test_duration=metrics.test_duration
            )
        return result

    def time_series_metrics(self) -> List[TimeSeriesMetrics]:
        """Per-interval metrics sorted by bucket.

        Note: buckets are aligned to absolute epoch multiples of
        interval_seconds (not to the first sample's timestamp), so bucket
        boundaries may differ from MetricsCalculator's output.
        """
        if self._overall.count == 0:
            raise ValueError("Cannot calculate metrics for empty test results")
        result = []
        for key in sorted(self._intervals):
            bucket = self._intervals[key]
            result.append(TimeSeriesMetrics(
                timestamp=datetime.fromtimestamp(key * self.interval_seconds),
                active_threads=len(bucket.threads),
                throughput=bucket.count / self.interval_seconds,
                average_response_time=bucket.rt_sum / bucket.count if bucket.count else 0,
                error_rate=(bucket.error_count / bucket.count) * 100 if bucket.count else 0
            ))
        return result

    def error_analysis(self) -> Dict:
        if not self._error_types:
            return {"error_types": {}, "error_patterns": []}

        error_patterns = []
        if self._intervals:
            first_key = min(self._intervals)
            last_key = max(self._intervals)
            interval_errors = [self._error_intervals.get(k, 0)
                               for k in range(first_key, last_key + 1)]
            avg_errors = sum(interval_errors) / len(interval_errors) if interval_errors else 0

            for i, error_count in enumerate(interval_errors):
                if error_count > 2 * avg_errors and error_count > 1:
                    spike_time = datetime.fromtimestamp((first_key + i) * self.interval_seconds)
                    error_patterns.append({
                        "type": "spike",
                        "timestamp": spike_time.isoformat(),
                        "error_count": error_count
                    })

        return {
            "error_types": dict(self._error_types),
            "error_patterns": error_patterns
        }
