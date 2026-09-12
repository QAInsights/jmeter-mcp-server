"""
Tests for live JTL metrics.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from runs.live_metrics import read_live_metrics

HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"


def _row(ts, elapsed, success="true", threads="4", label="EP"):
    return f"{ts},{elapsed},{label},200,OK,T-1,text,{success},,1000,500,4,{threads},http://x,{elapsed},0,10"


class TestLiveMetrics(unittest.TestCase):
    def _write(self, text, suffix='.jtl'):
        f = tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return Path(f.name)

    def test_known_values(self):
        # 100 rows: elapsed = 1..100, every 5th is an error
        rows = [_row(1625097600000 + i * 100, i + 1,
                     success="false" if (i + 1) % 5 == 0 else "true",
                     threads="7")
                for i in range(100)]
        path = self._write(HEADER + "\n" + "\n".join(rows) + "\n")
        m = read_live_metrics(path, window_lines=2000)
        self.assertTrue(m["supported"])
        self.assertEqual(m["total_samples"], 100)
        self.assertEqual(m["recent_samples"], 100)
        self.assertAlmostEqual(m["recent_error_rate_pct"], 20.0)
        self.assertAlmostEqual(m["recent_avg_response_ms"], 50.5)
        # p95 of 1..100 via interpolation: index = 0.95*99 = 94.05 -> 95 + .05
        self.assertAlmostEqual(m["recent_p95_response_ms"], 95.05)
        self.assertEqual(m["active_threads"], 7)
        self.assertEqual(m["last_sample_time"],
                         datetime.fromtimestamp(1625097600000 / 1000 + 99 * 0.1).isoformat())
        self.assertEqual(m["file_size_bytes"], path.stat().st_size)

    def test_window_limits_recent(self):
        rows = [_row(1625097600000 + i * 100, 10) for i in range(5000)]
        path = self._write(HEADER + "\n" + "\n".join(rows) + "\n")
        m = read_live_metrics(path, window_lines=100)
        self.assertEqual(m["total_samples"], 5000)
        self.assertLessEqual(m["recent_samples"], 100)
        self.assertGreater(m["recent_samples"], 0)

    def test_xml_unsupported(self):
        path = self._write('<?xml version="1.0"?><testResults/>', suffix='.xml')
        m = read_live_metrics(path)
        self.assertFalse(m["supported"])

    def test_truncated_last_line(self):
        rows = [_row(1625097600000 + i * 100, 100) for i in range(10)]
        text = HEADER + "\n" + "\n".join(rows) + "\n1625097650"  # partial line
        path = self._write(text)
        m = read_live_metrics(path)
        self.assertTrue(m["supported"])
        self.assertEqual(m["total_samples"], 11)  # partial last line counted
        # but it is skipped in the recent-window stats
        self.assertEqual(m["recent_samples"], 10)

    def test_missing_file(self):
        m = read_live_metrics("/nonexistent/x.jtl")
        self.assertFalse(m["supported"])


if __name__ == '__main__':
    unittest.main()
