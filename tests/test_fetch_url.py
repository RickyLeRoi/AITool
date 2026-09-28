# tests/test_fetch_url.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import fetch_url


class TestFetchUrl(unittest.TestCase):
    def test_unreachable_host_returns_error_string_not_exception(self):
        result = fetch_url.digest("http://127.0.0.1:1/does-not-exist", timeout=2)
        self.assertIn("error fetching", result)

    def test_strip_tags_removes_markup(self):
        html = "<html><head><style>body{color:red}</style></head><body><p>Hello <b>World</b></p></body></html>"
        stripped = fetch_url.TAG_RE.sub(" ", html)
        self.assertNotIn("<p>", stripped)
        self.assertIn("Hello", stripped)
        self.assertIn("World", stripped)
        self.assertNotIn("color:red", stripped)


if __name__ == "__main__":
    unittest.main()
