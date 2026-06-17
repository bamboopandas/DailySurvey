import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from auto_search.collectors.arxiv import parse_arxiv_feed
from auto_search.collectors.rss import collect, parse_feed


class CollectorParsingTest(unittest.TestCase):
    def test_parse_arxiv_feed(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <updated>2026-04-27T10:00:00Z</updated>
    <published>2026-04-27T09:00:00Z</published>
    <title>LLM Recommender Systems</title>
    <summary>A paper about recommendation.</summary>
    <author><name>Yongfeng Zhang</name></author>
    <link href="https://arxiv.org/abs/2601.00001" rel="alternate" type="text/html"/>
    <category term="cs.IR"/>
  </entry>
</feed>"""
        items = parse_arxiv_feed(xml, "arxiv", "recsys_research")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "LLM Recommender Systems")
        self.assertEqual(items[0]["external_ids"]["arxiv"], "2601.00001v1")
        self.assertEqual(items[0]["authors"], ["Yongfeng Zhang"])

    def test_parse_rss_feed(self):
        xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Blog</title>
    <item>
      <title>New AI Tool</title>
      <link>https://example.com/tool</link>
      <pubDate>Mon, 27 Apr 2026 10:00:00 GMT</pubDate>
      <description>Useful launch.</description>
    </item>
  </channel>
</rss>"""
        items = parse_feed(xml, "Example", "blog", "ai_social_tools")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://example.com/tool")
        self.assertEqual(items[0]["section_hint"], "ai_social_tools")

    def test_rss_collect_passes_timeout_config(self):
        xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Blog</title>
    <item>
      <title>New AI Tool</title>
      <link>https://example.com/tool</link>
      <pubDate>Mon, 27 Apr 2026 10:00:00 GMT</pubDate>
      <description>Useful launch.</description>
    </item>
  </channel>
</rss>"""
        source = {
            "type": "rss",
            "timeout_seconds": 3,
            "retries": 0,
            "feeds": [{"name": "Example", "url": "https://example.com/feed.xml"}],
        }
        with TemporaryDirectory() as tmpdir:
            context = {
                "lookback_start": datetime(2026, 4, 27, tzinfo=timezone.utc),
                "cache_dir": Path(tmpdir),
            }
            with patch("auto_search.collectors.rss.http.request_text_cached", return_value=xml) as request:
                items, warnings = collect(source, context)

        self.assertEqual(len(items), 1)
        self.assertEqual(warnings, [])
        self.assertEqual(request.call_args.kwargs["timeout"], 3)
        self.assertEqual(request.call_args.kwargs["retries"], 0)


if __name__ == "__main__":
    unittest.main()
