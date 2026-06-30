"""Regression tests for graph_converter._extract_json_value.
Run: python3 -m unittest discover tests
These lock in behavior so the balanced-scan refactor can be verified.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_converter import _extract_json_value


class TestExtractJsonValue(unittest.TestCase):
    def _parse(self, text, start=0):
        return json.loads(_extract_json_value(text, start))

    def test_simple_array(self):
        self.assertEqual(self._parse('[1,2,3];'), [1, 2, 3])

    def test_simple_object(self):
        self.assertEqual(self._parse('{"a":1,"b":2}'), {"a": 1, "b": 2})

    def test_nested(self):
        self.assertEqual(self._parse('[{"a":[1,2]},{"b":3}]'),
                         [{"a": [1, 2]}, {"b": 3}])

    def test_brackets_inside_string(self):
        # ']' and '}' inside string literals must not end the value early
        self.assertEqual(self._parse('["a]b","c}d"]'), ["a]b", "c}d"])

    def test_escaped_quote_in_string(self):
        self.assertEqual(self._parse(r'["a\"]b"]'), ['a"]b'])

    def test_leading_whitespace(self):
        self.assertEqual(self._parse('   \n\t[1]'), [1])

    def test_trailing_content_ignored(self):
        # Should stop at the matching close bracket, ignoring trailing JS
        self.assertEqual(self._parse('[1,2]) ;\nmore junk'), [1, 2])

    def test_object_with_array_values(self):
        self.assertEqual(self._parse('{"x":[1,{"y":2}],"z":"}"}'),
                         {"x": [1, {"y": 2}], "z": "}"})


if __name__ == "__main__":
    unittest.main()
