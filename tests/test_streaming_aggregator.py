"""
Tests for the streaming metrics aggregator.
"""

import random
import statistics
import unittest
from collections import Counter
from datetime import datetime, timedelta

from analyzer.metrics.calculator import MetricsCalculator
from analyzer.metrics.streaming import StreamingAggregator, percentile_from_histogram
from analyzer.models import Sample, TestResults


def _make_samples(n=2000, seed=42):
    rng = random.Random(seed)
    base = datetime(2023, 1, 1, 12, 0, 0)
    labels = ["EP-A", "EP-B", "EP-C"]
    threads = ["T-1", "T-2", "T-3", "T-4"]
    samples = []
    for i in range(n):
        success = rng.random() >= 0.10
        samples.append(Sample(
            timestamp=base + timedelta(seconds=rng.random() * 60,
                                       milliseconds=rng.randint(0, 999)),
            label=rng.choice(labels),
            response_time=rng.randint(50, 2000),
            success=success,
            response_code="200" if success else "500",
            error_message="" if success else (rng.choice(["Timeout", ""]) or None),
            thread_name=rng.choice(threads),
            bytes_received=1000,
            bytes_sent=500,
            latency=10,
            connect_time=5,
        ))
    return samples


def _test_results(samples):
    tr = TestResults()
    for s in samples:
        tr.add_sample(s)
    return tr


_METRIC_FIELDS = [
    'total_samples', 'error_count', 'error_rate', 'average_response_time',
    'median_response_time', 'percentile_90', 'percentile_95', 'percentile_99',
    'min_response_time', 'max_response_time', 'throughput', 'test_duration',
]


class TestStreamingAggregator(unittest.TestCase):
    def setUp(self):
        self.samples = _make_samples()
        self.agg = StreamingAggregator().consume(self.samples)
        self.calc = MetricsCalculator()
        self.tr = _test_results(self.samples)

    def test_overall_metrics_match(self):
        expected = self.calc.calculate_overall_metrics(self.tr)
        actual = self.agg.overall_metrics()
        for field in _METRIC_FIELDS:
            self.assertAlmostEqual(getattr(actual, field), getattr(expected, field),
                                   places=9, msg=field)

    def test_endpoint_metrics_match(self):
        expected = self.calc.calculate_endpoint_metrics(self.tr)
        actual = self.agg.endpoint_metrics()
        self.assertEqual(set(actual), set(expected))
        for label in expected:
            for field in _METRIC_FIELDS:
                self.assertAlmostEqual(getattr(actual[label], field),
                                       getattr(expected[label], field),
                                       places=9, msg=f"{label}.{field}")
            self.assertEqual(actual[label].endpoint, label)

    def test_error_types_match(self):
        expected = {}
        for s in self.samples:
            if not s.success:
                msg = s.error_message or f"HTTP {s.response_code}"
                expected[msg] = expected.get(msg, 0) + 1
        self.assertEqual(self.agg.error_analysis()["error_types"], expected)

    def test_start_end_times(self):
        self.assertEqual(self.agg.start_time, self.tr.start_time)
        self.assertEqual(self.agg.end_time, self.tr.end_time)

    def test_empty_raises_valueerror(self):
        with self.assertRaises(ValueError):
            StreamingAggregator().overall_metrics()
        with self.assertRaises(ValueError):
            StreamingAggregator().endpoint_metrics()
        with self.assertRaises(ValueError):
            StreamingAggregator().time_series_metrics()

    def test_no_errors_error_analysis(self):
        samples = [Sample(timestamp=datetime(2023, 1, 1), label="x",
                          response_time=100, success=True, response_code="200")]
        agg = StreamingAggregator().consume(samples)
        self.assertEqual(agg.error_analysis(), {"error_types": {}, "error_patterns": []})


class TestTimeSeries(unittest.TestCase):
    def test_epoch_aligned_buckets(self):
        base = datetime(2023, 1, 1, 12, 0, 3)  # not aligned to a 5s boundary
        samples = []
        for i in range(10):
            samples.append(Sample(
                timestamp=base + timedelta(seconds=i * 2, milliseconds=100),
                label="EP", response_time=100 + i * 10,
                success=(i != 4), response_code="200" if i != 4 else "500",
                thread_name=f"T-{i % 3 + 1}"))
        ts = StreamingAggregator(interval_seconds=5).consume(samples).time_series_metrics()
        self.assertTrue(len(ts) >= 3)
        for m in ts:
            # timestamps aligned to epoch multiples of 5
            self.assertEqual(m.timestamp.timestamp() % 5, 0)
            self.assertEqual(m.timestamp.microsecond, 0)
        # first bucket covers epoch seconds ...00-05 -> only the sample at :03
        self.assertEqual(ts[0].timestamp, datetime.fromtimestamp(
            int(base.timestamp() // 5) * 5))
        # throughput = count / 5
        self.assertAlmostEqual(ts[0].throughput, ts_count(samples, ts[0]) / 5)
        # active_threads counts distinct thread names in the bucket
        self.assertEqual(ts[0].active_threads, 1)
        # second bucket (:05-:10) holds samples i=1,2,3 -> threads T-2,T-3,T-1
        self.assertEqual(ts[1].active_threads, 3)
        # error rate percent
        for m in ts:
            self.assertGreaterEqual(m.error_rate, 0)

    def test_throughput_and_threads(self):
        base = datetime.fromtimestamp(1625097600)  # aligned
        samples = [Sample(timestamp=base + timedelta(seconds=i),
                          label="EP", response_time=100, success=True,
                          response_code="200", thread_name=f"T-{i % 4}")
                   for i in range(5)]
        ts = StreamingAggregator(interval_seconds=5).consume(samples).time_series_metrics()
        self.assertEqual(len(ts), 1)
        self.assertAlmostEqual(ts[0].throughput, 5 / 5)
        self.assertEqual(ts[0].active_threads, 4)
        self.assertEqual(ts[0].average_response_time, 100)
        self.assertEqual(ts[0].error_rate, 0)


def ts_count(samples, metric):
    # helper: count samples falling into the bucket starting at metric.timestamp
    start = metric.timestamp.timestamp()
    return sum(1 for s in samples if start <= s.timestamp.timestamp() < start + 5)


class TestPercentileFromHistogram(unittest.TestCase):
    def test_matches_calculator(self):
        calc = MetricsCalculator()
        rng = random.Random(7)
        for n in (1, 2, 3, 7, 15, 100):
            values = sorted(rng.randint(1, 500) for _ in range(n))
            hist = Counter(values)
            for p in (0, 50, 90, 95, 99, 100):
                expected = calc._calculate_percentile(values, p)
                actual = percentile_from_histogram(hist, n, p)
                self.assertAlmostEqual(actual, expected, places=9,
                                       msg=f"n={n} p={p}")

    def test_median_matches_statistics(self):
        rng = random.Random(11)
        for n in (1, 2, 3, 4, 99, 100):
            values = [rng.randint(1, 100) for _ in range(n)]
            hist = Counter(values)
            self.assertAlmostEqual(
                percentile_from_histogram(hist, n, 50),
                statistics.median(values), places=9)

    def test_empty(self):
        self.assertEqual(percentile_from_histogram(Counter(), 0, 90), 0)


if __name__ == '__main__':
    unittest.main()
