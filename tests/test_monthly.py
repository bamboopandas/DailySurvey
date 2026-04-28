import tempfile
import unittest
from pathlib import Path

from auto_search.config import write_json
from auto_search.monthly import prepare_monthly_input, previous_month


class MonthlyTest(unittest.TestCase):
    def test_previous_month(self):
        self.assertEqual(previous_month(__import__("datetime").date(2026, 5, 1)), "2026-04")

    def test_prepare_monthly_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            day = runs / "2026-04-28"
            day.mkdir(parents=True)
            write_json(
                day / "brief.json",
                {
                    "report_type": "daily",
                    "date": "2026-04-28",
                    "page_summary": "日报摘要",
                    "sections": [
                        {
                            "id": "recsys_research",
                            "title": "推荐系统研究动态",
                            "section_summary": "新闻摘要",
                            "cards": [{"candidate_id": "c1", "title": "Paper", "url": "https://example.com"}],
                        }
                    ],
                },
            )
            write_json(
                day / "candidates.json",
                {
                    "date": "2026-04-28",
                    "candidates_by_section": {
                        "recsys_research": [
                            {
                                "id": "c1",
                                "title": "Paper",
                                "url": "https://example.com",
                                "score": 10,
                                "evidence": [{"label": "source", "url": "https://example.com"}],
                            }
                        ]
                    },
                },
            )
            output = prepare_monthly_input("2026-04", runs_dir=runs)
            self.assertTrue(output.exists())
            text = output.read_text(encoding="utf-8")
            self.assertIn("monthly", text)
            self.assertIn("日报摘要", text)


if __name__ == "__main__":
    unittest.main()

