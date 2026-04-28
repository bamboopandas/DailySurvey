from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import DEFAULT_RUNS_DIR, read_json, write_json
from .schema import SECTIONS


def previous_month(reference: Optional[dt.date] = None) -> str:
    reference = reference or dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    first_day = reference.replace(day=1)
    last_previous = first_day - dt.timedelta(days=1)
    return last_previous.strftime("%Y-%m")


def prepare_monthly_input(month: Optional[str], runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    month = month or previous_month()
    output_dir = runs_dir / "monthly" / month
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_reports, daily_candidates = load_month_data(month, runs_dir)
    payload = {
        "report_type": "monthly",
        "month": month,
        "date": month,
        "title": f"{month} AI / 推荐系统研究月报",
        "section_labels": SECTIONS,
        "coverage": {
            "daily_report_count": len(daily_reports),
            "candidate_count": sum(len(day.get("candidates", [])) for day in daily_candidates),
            "days": sorted({day.get("date") for day in daily_reports if day.get("date")}),
        },
        "instructions_for_codex": monthly_instructions(month),
        "daily_reports": compact_daily_reports(daily_reports),
        "top_candidates_by_section": compact_candidates(daily_candidates),
    }
    output_path = output_dir / "monthly_input.json"
    write_json(output_path, payload)
    return output_path


def load_month_data(month: str, runs_dir: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    daily_reports: List[Dict[str, Any]] = []
    daily_candidates: List[Dict[str, Any]] = []
    for run_dir in sorted(runs_dir.glob(f"{month}-??")):
        brief_path = run_dir / "brief.json"
        candidates_path = run_dir / "candidates.json"
        if brief_path.exists():
            brief = read_json(brief_path)
            if not brief.get("_fallback_brief"):
                daily_reports.append(brief)
        if candidates_path.exists():
            daily_candidates.append(read_json(candidates_path))
    return daily_reports, daily_candidates


def compact_daily_reports(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compacted = []
    for report in reports:
        compacted.append(
            {
                "date": report.get("date"),
                "page_summary": report.get("page_summary"),
                "sections": [
                    {
                        "id": section.get("id"),
                        "title": section.get("title"),
                        "section_summary": section.get("section_summary") or section.get("trend_summary"),
                        "cards": [
                            {
                                "candidate_id": card.get("candidate_id"),
                                "title": card.get("title"),
                                "url": card.get("url"),
                                "summary_cn": card.get("summary_cn"),
                                "why_it_matters": card.get("why_it_matters"),
                                "recsys_inspiration": card.get("recsys_inspiration"),
                            }
                            for card in section.get("cards", [])[:5]
                        ],
                    }
                    for section in report.get("sections", [])
                ],
            }
        )
    return compacted


def compact_candidates(candidate_days: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_section: Dict[str, Dict[str, Dict[str, Any]]] = {section_id: {} for section_id in SECTIONS}
    for day in candidate_days:
        for section_id, items in (day.get("candidates_by_section") or {}).items():
            section_items = by_section.setdefault(section_id, {})
            for item in items:
                item_id = item.get("id") or item.get("url") or item.get("title")
                if not item_id or item_id in section_items:
                    continue
                section_items[item_id] = {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "source_type": item.get("source_type"),
                    "published_at": item.get("published_at"),
                    "summary": item.get("summary"),
                    "score": item.get("score"),
                    "metrics": item.get("metrics", {}),
                    "evidence": item.get("evidence", []),
                }
    return {
        section_id: sorted(items.values(), key=lambda item: item.get("score") or 0, reverse=True)[:50]
        for section_id, items in by_section.items()
    }


def monthly_instructions(month: str) -> Dict[str, Any]:
    return {
        "output_file": "monthly_brief.json",
        "language": "zh-CN",
        "schema": {
            "report_type": "monthly",
            "date": month,
            "title": f"{month} AI / 推荐系统研究月报",
            "page_summary": "Newspaper-magazine style monthly lead: the month's dominant shifts, why they matter, and what changed from the beginning to the end of the month.",
            "sections": [
                {
                    "id": "one of recsys_research,llm_hotspots,data_centric_ai,ai_social_tools",
                    "title": "Chinese section title",
                    "trend_summary": "A real monthly trend analysis grounded in repeated evidence across days.",
                    "trend_bullets": ["3-6 evidence-backed trend bullets"],
                    "cards": [
                        {
                            "candidate_id": "candidate id or manual:<stable-slug>",
                            "title": "representative item title",
                            "summary_cn": "why this item represents the monthly trend",
                            "why_it_matters": "why it matters at month scale",
                            "recsys_inspiration": "what recommender-system researchers can do next",
                            "url": "source URL",
                            "citations": [{"label": "source label", "url": "source URL"}],
                        }
                    ],
                }
            ],
        },
        "selection_policy": [
            "This is a monthly report, so trend language is required and must be grounded in repeated evidence across days or multiple independent sources.",
            "Do not merely concatenate daily summaries. Identify what changed, what persisted, and what turned out to be noise.",
            "Write like a technology magazine reporter: clear thesis, evidence, implications, and caveats.",
            "Each section should pick up to five representative items, not necessarily the highest daily score.",
            "Explicitly separate strong trends from weak signals and one-off events.",
            "If local daily reports are insufficient, use the Codex app's own search/browsing capability to supplement public sources and cite them.",
        ],
    }

