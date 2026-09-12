"""
Large-file streaming test: analyze a 300k-row JTL with bounded memory.
"""

import csv
import os
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path

from analyzer.analyzer import TestResultsAnalyzer
from analyzer.cache import AnalysisCache

CSV_HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"

ROW_COUNT = 300_000


def _generate_jtl(path, rows=ROW_COUNT):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER.split(','))
        for i in range(rows):
            ts = 1625097600000 + i * 100
            label = f"EP-{i % 5}"
            success = "false" if i % 20 == 0 else "true"
            rc = "500" if success == "false" else "200"
            rm = "ERR" if success == "false" else "OK"
            elapsed = 50 + (i % 1500)
            writer.writerow([ts, elapsed, label, rc, rm, f"T-{i % 8}", "text",
                             success, "", 1000, 500, 8, 8, "http://x", elapsed, 0, 10])


class TestLargeFileStreaming(unittest.TestCase):
    def test_300k_rows_bounded_memory(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "big.jtl"
            _generate_jtl(path)

            analyzer = TestResultsAnalyzer(cache=AnalysisCache())
            tracemalloc.start()
            start = time.time()
            result = analyzer.analyze_file(path, detailed=True)
            elapsed = time.time() - start
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            self.assertEqual(result["summary"]["total_samples"], ROW_COUNT)
            peak_mb = peak / (1024 * 1024)
            print(f"\n300k-row analysis: {elapsed:.2f}s, peak memory {peak_mb:.1f} MB")
            self.assertLess(peak_mb, 60)


if __name__ == '__main__':
    unittest.main()
