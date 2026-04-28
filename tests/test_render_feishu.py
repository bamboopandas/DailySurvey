import tempfile
import unittest
from pathlib import Path

from auto_search.config import write_json
from auto_search.feishu import sign
from auto_search.render import build_feishu_card, render_outputs, report_public_url
from auto_search.schema import candidate


class RenderFeishuTest(unittest.TestCase):
    def test_build_feishu_card_shape(self):
        brief = {
            "date": "2026-04-28",
            "title": "每日 AI / 推荐系统情报简报",
            "page_summary": "总览",
            "sections": [
                {
                    "id": "recsys_research",
                    "title": "推荐系统研究动态",
                    "trend_summary": "趋势",
                    "cards": [{"title": "Paper", "url": "https://example.com", "summary_cn": "摘要"}],
                }
            ],
        }
        card = build_feishu_card(brief, "https://example.com/reports/2026-04-28/")
        self.assertEqual(card["msg_type"], "interactive")
        self.assertIn("elements", card["card"])

    def test_render_outputs_writes_report_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "runs" / "2026-04-28"
            run_dir.mkdir(parents=True)
            item = candidate(title="Paper", url="https://example.com", source="arxiv", source_type="paper")
            write_json(run_dir / "candidates.json", {"candidates": [item]})
            write_json(
                run_dir / "brief.json",
                {
                    "date": "2026-04-28",
                    "sections": [
                        {
                            "id": "recsys_research",
                            "cards": [{"candidate_id": item["id"], "summary_cn": "摘要"}],
                        }
                    ],
                },
            )
            outputs = render_outputs(run_dir / "brief.json", docs_dir=root / "docs")
            self.assertTrue(outputs["report"].exists())
            self.assertTrue(outputs["card"].exists())
            self.assertIn("noindex", outputs["report"].read_text(encoding="utf-8"))

    def test_feishu_sign_is_stable(self):
        self.assertEqual(sign("123", "secret"), sign("123", "secret"))
        self.assertNotEqual(sign("123", "secret"), sign("124", "secret"))

    def test_monthly_report_url_uses_monthly_path(self):
        self.assertEqual(
            report_public_url("2026-04", "monthly"),
            "docs/monthly/2026-04/index.html",
        )


if __name__ == "__main__":
    unittest.main()
