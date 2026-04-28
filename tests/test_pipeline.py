import tempfile
import unittest
from pathlib import Path

from auto_search.config import write_json
from auto_search.pipeline import dedupe_items, mark_seen_from_brief, score_sections
from auto_search.schema import candidate, parse_datetime


class PipelineTest(unittest.TestCase):
    def test_dedupe_merges_arxiv_and_semantic_scholar(self):
        left = candidate(
            title="A Recommender Paper",
            url="https://arxiv.org/abs/2601.1",
            source="arxiv",
            source_type="paper",
            external_ids={"arxiv": "2601.1"},
            evidence=[{"label": "arXiv", "url": "https://arxiv.org/abs/2601.1"}],
        )
        right = candidate(
            title="A Recommender Paper",
            url="https://semanticscholar.org/paper/x",
            source="semantic_scholar",
            source_type="paper",
            external_ids={"arxiv": "2601.1", "semantic_scholar": "x"},
            evidence=[{"label": "Semantic Scholar", "url": "https://semanticscholar.org/paper/x"}],
        )
        merged = dedupe_items([left, right])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["evidence"]), 2)
        self.assertEqual(merged[0]["external_ids"]["semantic_scholar"], "x")

    def test_scoring_boosts_tracked_researcher(self):
        item = candidate(
            title="New LLM4Rec Method",
            url="https://example.com",
            source="arxiv",
            source_type="paper",
            authors=["Julian McAuley"],
            summary="A sequential recommendation paper.",
        )
        config = {
            "keywords": {
                "tracked_researcher_bonus": 6,
                "tracked_team_bonus": 4,
                "sections": {
                    "recsys_research": [{"term": "recommendation", "weight": 3}],
                    "llm_hotspots": [{"term": "LLM", "weight": 2}],
                    "data_centric_ai": [],
                    "ai_social_tools": [],
                },
            },
            "people": {
                "researchers": [{"name": "Julian McAuley", "aliases": ["Julian McAuley"]}],
                "industry_teams": [],
            },
        }
        scores = score_sections(item, config)
        self.assertGreater(scores["recsys_research"], scores["llm_hotspots"])

    def test_mark_seen_from_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            item = candidate(title="Paper", url="https://example.com", source="arxiv", source_type="paper")
            candidates = {item["id"]: item}
            brief = {"sections": [{"cards": [{"candidate_id": item["id"]}]}]}
            mark_seen_from_brief(brief, candidates, state_dir)
            data = (state_dir / "seen.json").read_text(encoding="utf-8")
            self.assertIn("Paper", data)

    def test_mark_seen_from_manual_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            brief = {
                "sections": [
                    {
                        "cards": [
                            {
                                "candidate_id": "manual:new-tool",
                                "title": "Manual Tool",
                                "url": "https://example.com/tool",
                            }
                        ]
                    }
                ]
            }
            mark_seen_from_brief(brief, {}, state_dir)
            data = (state_dir / "seen.json").read_text(encoding="utf-8")
            self.assertIn("Manual Tool", data)

    def test_parse_long_timestamp(self):
        parsed = parse_datetime("17700000000000")
        self.assertIsNotNone(parsed)
        self.assertLess(parsed.year, 2100)

    def test_parse_long_numeric_timestamp(self):
        parsed = parse_datetime(17700000000000)
        self.assertIsNotNone(parsed)
        self.assertLess(parsed.year, 2100)


if __name__ == "__main__":
    unittest.main()
