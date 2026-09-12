"""
Tests for streaming iter_samples parsers (CSV and XML).
"""

import inspect
import itertools
import os
import tempfile
import unittest

from analyzer.parser.csv_parser import CSVJTLParser
from analyzer.parser.xml_parser import XMLJTLParser

CSV_HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"


def _csv_row(ts, elapsed=100, label="EP", rc="200", rm="OK", tn="T-1", success="true"):
    return f"{ts},{elapsed},{label},{rc},{rm},{tn},text,{success},,1000,500,1,1,http://x/{label},{elapsed},0,10"


XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<testResults version="1.2">
<httpSample t="100" lt="90" ts="1625097600000" s="true" lb="A" rc="200" rm="OK" tn="T-1" by="1000" sby="500" ct="10"/>
<httpSample t="200" lt="180" ts="1625097601000" s="false" lb="B" rc="500" rm="ERR" tn="T-2" by="2000" sby="600" ct="20"/>
<sample t="150" lt="140" ts="1625097602000" s="true" lb="A" rc="200" rm="OK" tn="T-1" by="500" sby="250" ct="5"/>
</testResults>
"""


class TestCSVIterSamples(unittest.TestCase):
    def setUp(self):
        self.parser = CSVJTLParser()

    def _write(self, content, suffix='.csv'):
        f = tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False)
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_iter_samples_matches_parse_file(self):
        path = self._write(CSV_HEADER + "\n" + "\n".join(
            _csv_row(1625097600000 + i * 1000) for i in range(5)) + "\n")
        streamed = list(self.parser.iter_samples(path))
        parsed = self.parser.parse_file(path).samples
        self.assertEqual(streamed, parsed)
        self.assertEqual(len(streamed), 5)

    def test_iter_samples_is_lazy(self):
        path = self._write(CSV_HEADER + "\n" + "\n".join(
            _csv_row(1625097600000 + i * 100) for i in range(10000)) + "\n")
        it = self.parser.iter_samples(path)
        self.assertTrue(inspect.isgenerator(it))
        first3 = list(itertools.islice(it, 3))
        self.assertEqual(len(first3), 3)

    def test_malformed_row_skipped_with_warning(self):
        path = self._write(CSV_HEADER + "\n" + _csv_row(1625097600000) + "\n"
                           + "not,a,valid,row\n" + _csv_row(1625097601000) + "\n")
        with self.assertLogs('analyzer.parser.csv_parser', level='WARNING') as cm:
            samples = list(self.parser.iter_samples(path))
        self.assertEqual(len(samples), 2)
        self.assertTrue(any('Error parsing row' in m for m in cm.output))

    def test_wrong_format_raises_valueerror(self):
        path = self._write('<?xml version="1.0"?><testResults/>\n', suffix='.xml')
        with self.assertRaises(ValueError):
            list(self.parser.iter_samples(path))

    def test_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            list(self.parser.iter_samples('/nonexistent/file.csv'))


class TestXMLIterSamples(unittest.TestCase):
    def setUp(self):
        self.parser = XMLJTLParser()

    def _write(self, content, suffix='.xml'):
        f = tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False)
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_iter_samples_matches_parse_file(self):
        path = self._write(XML_TEMPLATE)
        streamed = list(self.parser.iter_samples(path))
        parsed = self.parser.parse_file(path).samples
        self.assertEqual(streamed, parsed)
        self.assertEqual(len(streamed), 3)
        self.assertEqual(streamed[1].error_message, "ERR")

    def test_iter_samples_is_generator(self):
        path = self._write(XML_TEMPLATE)
        self.assertTrue(inspect.isgenerator(self.parser.iter_samples(path)))

    def test_wrong_format_raises_valueerror(self):
        path = self._write(CSV_HEADER + "\n" + _csv_row(1625097600000) + "\n", suffix='.csv')
        with self.assertRaises(ValueError):
            list(self.parser.iter_samples(path))

    def test_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            list(self.parser.iter_samples('/nonexistent/file.xml'))

    def test_malformed_xml_raises_valueerror(self):
        path = self._write('<?xml version="1.0"?><testResults><httpSample t="1"', suffix='.xml')
        with self.assertRaises(ValueError):
            list(self.parser.iter_samples(path))


if __name__ == '__main__':
    unittest.main()
