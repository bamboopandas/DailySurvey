import unittest
from contextlib import contextmanager
from unittest.mock import patch

from auto_search import http


class HttpTest(unittest.TestCase):
    def test_request_text_wraps_hard_timeout(self):
        @contextmanager
        def deadline(_timeout):
            raise http._HardTimeout("request exceeded deadline")
            yield

        with patch("auto_search.http._request_deadline", deadline):
            with self.assertRaises(http.FetchError) as raised:
                http.request_text("https://example.com/feed.xml", timeout=1, retries=0)

        self.assertIn("failed to fetch https://example.com/feed.xml", str(raised.exception))
        self.assertIn("request exceeded deadline", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
