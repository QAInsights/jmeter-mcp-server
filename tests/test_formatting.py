"""
Tests for output.formatting helpers.
"""

import dataclasses
import enum
import json
import unittest
from datetime import datetime
from pathlib import Path

from output.formatting import json_error, json_ok, normalize_format, to_json


class _Color(enum.Enum):
    RED = "red"


@dataclasses.dataclass
class _Point:
    x: int
    y: int


class _WithToDict:
    def to_dict(self):
        return {"a": 1}


class TestToJson(unittest.TestCase):
    def test_types(self):
        obj = {
            "dt": datetime(2023, 1, 1, 12, 0, 0),
            "path": Path("/tmp/x"),
            "color": _Color.RED,
            "tags": {"b", "a"},
            "tup": (1, 2),
            "point": _Point(1, 2),
            "obj": _WithToDict(),
        }
        data = json.loads(to_json(obj))
        self.assertEqual(data["dt"], "2023-01-01T12:00:00")
        self.assertEqual(data["path"], "/tmp/x")
        self.assertEqual(data["color"], "red")
        self.assertEqual(sorted(data["tags"]), ["a", "b"])
        self.assertEqual(data["tup"], [1, 2])
        self.assertEqual(data["point"], {"x": 1, "y": 2})
        self.assertEqual(data["obj"], {"a": 1})

    def test_unicode_not_escaped(self):
        self.assertIn("café", to_json({"x": "café"}))

    def test_envelopes(self):
        self.assertEqual(json.loads(json_ok({"a": 1})), {"ok": True, "data": {"a": 1}})
        self.assertEqual(json.loads(json_error("bad", run_id="r")),
                         {"ok": False, "error": "bad", "run_id": "r"})


class TestNormalizeFormat(unittest.TestCase):
    def test_values(self):
        self.assertEqual(normalize_format(None), "markdown")
        self.assertEqual(normalize_format("markdown"), "markdown")
        self.assertEqual(normalize_format("MD"), "markdown")
        self.assertEqual(normalize_format(" JSON "), "json")
        with self.assertRaises(ValueError) as cm:
            normalize_format("xml")
        self.assertIn("format must be 'json' or 'markdown'", str(cm.exception))


if __name__ == '__main__':
    unittest.main()
