"""
Tests for the analysis results cache.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import analyzer.cache as cache_module
from analyzer.analyzer import TestResultsAnalyzer
from analyzer.cache import AnalysisCache, _cache_size_from_env, default_cache

CSV_HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"


def _csv_row(ts):
    return f"{ts},100,EP,200,OK,T-1,text,true,,1000,500,1,1,http://x,100,0,10"


class TestAnalysisCache(unittest.TestCase):
    def _write_jtl(self, dirpath, name="r.jtl", rows=3):
        p = Path(dirpath) / name
        p.write_text(CSV_HEADER + "\n" + "\n".join(
            _csv_row(1625097600000 + i * 1000) for i in range(rows)) + "\n")
        return p

    def test_miss_then_hit(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write_jtl(d)
            cache = AnalysisCache()
            self.assertIsNone(cache.get(p))
            self.assertEqual(cache.misses, 1)
            cache.put(p, {"summary": {"total_samples": 3}})
            self.assertEqual(cache.get(p)["summary"]["total_samples"], 3)
            self.assertEqual(cache.hits, 1)

    def test_modification_invalidates(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write_jtl(d)
            cache = AnalysisCache()
            cache.put(p, {"v": 1})
            # Append a row and bump mtime
            with open(p, 'a') as f:
                f.write(_csv_row(1625097610000) + "\n")
            st = p.stat()
            os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
            self.assertIsNone(cache.get(p))

    def test_lru_eviction(self):
        with tempfile.TemporaryDirectory() as d:
            cache = AnalysisCache(max_entries=2)
            p1 = self._write_jtl(d, "a.jtl")
            p2 = self._write_jtl(d, "b.jtl")
            p3 = self._write_jtl(d, "c.jtl")
            cache.put(p1, {"n": 1})
            cache.put(p2, {"n": 2})
            cache.get(p1)  # p1 now most-recently-used
            cache.put(p3, {"n": 3})  # evicts p2
            self.assertIsNone(cache.get(p2))
            self.assertIsNotNone(cache.get(p1))
            self.assertIsNotNone(cache.get(p3))
            self.assertEqual(len(cache), 2)

    def test_zero_max_entries_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write_jtl(d)
            cache = AnalysisCache(max_entries=0)
            cache.put(p, {"v": 1})
            self.assertEqual(len(cache), 0)
            self.assertIsNone(cache.get(p))

    def test_env_size_parsing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_cache_size_from_env(), 8)
        with mock.patch.dict(os.environ, {'JMETER_ANALYSIS_CACHE_SIZE': '4'}):
            self.assertEqual(_cache_size_from_env(), 4)
        with mock.patch.dict(os.environ, {'JMETER_ANALYSIS_CACHE_SIZE': 'abc'}):
            self.assertEqual(_cache_size_from_env(), 8)
        with mock.patch.dict(os.environ, {'JMETER_ANALYSIS_CACHE_SIZE': '0'}):
            self.assertEqual(_cache_size_from_env(), 0)
        with mock.patch.dict(os.environ, {'JMETER_ANALYSIS_CACHE_SIZE': '-3'}):
            self.assertEqual(_cache_size_from_env(), 8)

    def test_default_cache_singleton(self):
        cache_module._default_cache = None
        try:
            self.assertIs(default_cache(), default_cache())
        finally:
            cache_module._default_cache = None

    def test_analyzer_parses_once(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write_jtl(d)
            analyzer = TestResultsAnalyzer(cache=AnalysisCache())
            csv_parser = analyzer.parsers['csv']
            with mock.patch.object(csv_parser, 'iter_samples',
                                   wraps=csv_parser.iter_samples) as spy:
                r1 = analyzer.analyze_file(p, detailed=False)
                r2 = analyzer.analyze_file(p, detailed=True)
                self.assertEqual(spy.call_count, 1)
            self.assertNotIn('detailed', r1)
            self.assertIn('detailed', r2)
            self.assertEqual(r1['summary']['total_samples'], 3)

    def test_returned_dicts_independent(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write_jtl(d)
            analyzer = TestResultsAnalyzer(cache=AnalysisCache())
            r1 = analyzer.analyze_file(p, detailed=True)
            r1['summary']['total_samples'] = -1
            r1['detailed']['endpoints'].clear()
            r2 = analyzer.analyze_file(p, detailed=True)
            self.assertEqual(r2['summary']['total_samples'], 3)
            self.assertTrue(len(r2['detailed']['endpoints']) > 0)


if __name__ == '__main__':
    unittest.main()
