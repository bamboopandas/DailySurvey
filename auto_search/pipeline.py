from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .collectors import COLLECTORS
from .config import DEFAULT_STATE_DIR, load_config, read_json, write_json
from .schema import SECTIONS, candidate_id, dedupe_key, normalize_key, parse_datetime, text_blob, utc_now


def collect_candidates(
    *,
    lookback_hours: int,
    output_path: Path,
    state_dir: Path = DEFAULT_STATE_DIR,
    include_seen: bool = False,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    config = load_config()
    now = (now or utc_now()).astimezone(dt.timezone.utc)
    lookback_start = now - dt.timedelta(hours=lookback_hours)
    context = {"now": now, "lookback_start": lookback_start, "lookback_hours": lookback_hours}
    context["cache_dir"] = state_dir / "http_cache"

    warnings: List[str] = []
    raw_items: List[Dict[str, Any]] = []
    for source in config.get("sources", {}).get("sources", []):
        if not source.get("enabled", True):
            continue
        source_type = source.get("type")
        collector = COLLECTORS.get(source_type)
        if not collector:
            warnings.append(f"unknown source type: {source_type}")
            continue
        items, source_warnings = collector(source, context)
        raw_items.extend(items)
        warnings.extend(source_warnings)

    deduped = dedupe_items(raw_items)
    seen = load_seen(state_dir)
    scored: List[Dict[str, Any]] = []
    for item in deduped:
        item["section_scores"] = score_sections(item, config)
        section_id, score = best_section(item["section_scores"], item.get("section_hint"))
        item["section"] = section_id
        item["score"] = round(score + source_quality_bonus(item) + metric_bonus(item), 4)
        item["seen_before"] = dedupe_key(item) in seen.get("items", {})
        if item["seen_before"] and not include_seen and not has_material_update(item, seen["items"][dedupe_key(item)]):
            continue
        scored.append(item)

    scored.sort(key=lambda item: item.get("score", 0), reverse=True)
    by_section = {
        section_id: [item for item in scored if item.get("section") == section_id]
        for section_id in SECTIONS
    }
    output = {
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "date": now.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d"),
        "lookback_hours": lookback_hours,
        "lookback_start": lookback_start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "section_labels": SECTIONS,
        "instructions_for_codex": codex_brief_instructions(),
        "counts": {
            "raw": len(raw_items),
            "deduped": len(deduped),
            "after_seen_filter": len(scored),
        },
        "warnings": warnings,
        "candidates": scored,
        "candidates_by_section": {
            section_id: by_section[section_id][: int(config.get("keywords", {}).get("max_candidates_per_section", 30))]
            for section_id in SECTIONS
        },
    }
    write_json(output_path, output)
    return output


def dedupe_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = dedupe_key(item)
        item["dedupe_key"] = key
        if key not in grouped:
            grouped[key] = item
            continue
        grouped[key] = merge_items(grouped[key], item)
    return list(grouped.values())


def merge_items(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(left)
    if len(str(right.get("summary") or "")) > len(str(left.get("summary") or "")):
        merged["summary"] = right.get("summary")
    merged["authors"] = sorted(set((left.get("authors") or []) + (right.get("authors") or [])))
    merged["tags"] = sorted(set((left.get("tags") or []) + (right.get("tags") or [])))
    merged["evidence"] = _merge_evidence(left.get("evidence") or [], right.get("evidence") or [])
    merged["external_ids"] = {**(left.get("external_ids") or {}), **(right.get("external_ids") or {})}
    merged["metrics"] = _merge_metrics(left.get("metrics") or {}, right.get("metrics") or {})
    merged["sources"] = sorted(set((left.get("sources") or [left.get("source")]) + (right.get("sources") or [right.get("source")])))
    for field in ("updated_at", "published_at"):
        left_date = parse_datetime(left.get(field))
        right_date = parse_datetime(right.get(field))
        if right_date and (not left_date or right_date > left_date):
            merged[field] = right.get(field)
    if not merged.get("url") and right.get("url"):
        merged["url"] = right["url"]
    return merged


def score_sections(item: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, float]:
    keywords = config.get("keywords", {})
    people = config.get("people", {})
    blob = text_blob(item)
    scores = {section_id: 0.0 for section_id in SECTIONS}

    for section_id, terms in keywords.get("sections", {}).items():
        scores.setdefault(section_id, 0.0)
        scores[section_id] += keyword_score(blob, terms)

    for alias in _aliases(people.get("researchers", [])):
        if alias and normalize_key(alias) in blob:
            scores["recsys_research"] += float(keywords.get("tracked_researcher_bonus", 6.0))
    for alias in _aliases(people.get("industry_teams", [])):
        if alias and normalize_key(alias) in blob:
            scores["recsys_research"] += float(keywords.get("tracked_team_bonus", 4.0))
            scores["ai_social_tools"] += 1.0

    source_type = item.get("source_type")
    if source_type == "paper":
        scores["recsys_research"] += 0.5
        scores["llm_hotspots"] += 0.4
    if source_type in {"tool", "product", "social"}:
        scores["ai_social_tools"] += 3.0
    if item.get("section_hint") in scores:
        scores[item["section_hint"]] += 3.0
    return scores


def keyword_score(blob: str, terms: List[Any]) -> float:
    score = 0.0
    for term in terms:
        if isinstance(term, dict):
            text = normalize_key(str(term.get("term", "")))
            weight = float(term.get("weight", 1.0))
        else:
            text = normalize_key(str(term))
            weight = 1.0
        if text and text in blob:
            score += weight
    return score


def best_section(scores: Dict[str, float], hint: Optional[str]) -> Tuple[str, float]:
    if hint in SECTIONS and scores.get(hint, 0) >= 1.0:
        return hint, float(scores.get(hint, 0))
    section_id = max(SECTIONS, key=lambda key: scores.get(key, 0.0))
    return section_id, float(scores.get(section_id, 0.0))


def source_quality_bonus(item: Dict[str, Any]) -> float:
    source_type = item.get("source_type")
    if source_type == "paper":
        return 1.5
    if source_type in {"blog", "report"}:
        return 1.0
    if source_type in {"tool", "product"}:
        return 0.8
    if source_type == "social":
        return 0.6
    return 0.0


def metric_bonus(item: Dict[str, Any]) -> float:
    metrics = item.get("metrics") or {}
    score = 0.0
    for name in ("stars", "forks", "watchers", "citations", "points", "comments"):
        value = metrics.get(name)
        if isinstance(value, (int, float)) and value > 0:
            score += math.log10(value + 1) * 0.35
    return score


def load_seen(state_dir: Path = DEFAULT_STATE_DIR) -> Dict[str, Any]:
    path = state_dir / "seen.json"
    if not path.exists():
        return {"items": {}}
    data = read_json(path)
    if "items" not in data:
        data["items"] = {}
    return data


def mark_seen_from_brief(brief: Dict[str, Any], candidates: Dict[str, Dict[str, Any]], state_dir: Path = DEFAULT_STATE_DIR) -> Dict[str, Any]:
    seen = load_seen(state_dir)
    now = dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for section in brief.get("sections", []):
        for card in section.get("cards", []):
            candidate = candidates.get(card.get("candidate_id", ""))
            if not candidate:
                candidate = {
                    "title": card.get("title"),
                    "url": card.get("url"),
                    "published_at": card.get("published_at"),
                    "updated_at": card.get("updated_at"),
                    "external_ids": {},
                }
            key = dedupe_key(candidate)
            seen["items"][key] = {
                "title": candidate.get("title"),
                "url": candidate.get("url"),
                "first_sent_at": seen["items"].get(key, {}).get("first_sent_at", now),
                "last_sent_at": now,
                "published_at": candidate.get("published_at"),
                "updated_at": candidate.get("updated_at"),
            }
    write_json(state_dir / "seen.json", seen)
    return seen


def has_material_update(item: Dict[str, Any], seen_record: Dict[str, Any]) -> bool:
    item_updated = parse_datetime(item.get("updated_at") or item.get("published_at"))
    seen_updated = parse_datetime(seen_record.get("updated_at") or seen_record.get("published_at"))
    if item_updated and seen_updated and item_updated > seen_updated + dt.timedelta(hours=6):
        return True
    return False


def candidates_by_id(candidates_path: Path) -> Dict[str, Dict[str, Any]]:
    data = read_json(candidates_path)
    return {candidate_id(item): item for item in data.get("candidates", [])}


def codex_brief_instructions() -> Dict[str, Any]:
    return {
        "output_file": "brief.json",
        "language": "zh-CN",
        "schema": {
            "date": "YYYY-MM-DD",
            "title": "每日 AI / 推荐系统情报简报",
            "page_summary": "3-6 sentence overall summary in Chinese",
            "sections": [
                {
                    "id": "one of recsys_research,llm_hotspots,data_centric_ai,ai_social_tools",
                    "title": "Chinese section title",
                    "trend_summary": "A fuller Chinese trend brief. Prefer recall over brevity.",
                    "trend_bullets": ["3-6 concise bullets"],
                    "cards": [
                        {
                            "candidate_id": "must match a candidate id",
                            "title": "Chinese or original title",
                            "summary_cn": "2-3 sentence Chinese summary",
                            "why_it_matters": "why it matters now",
                            "recsys_inspiration": "possible inspiration for recommender-system research",
                            "url": "source URL",
                            "citations": [{"label": "source label", "url": "source URL"}],
                        }
                    ],
                }
            ],
        },
        "selection_policy": [
            "Write an overall narrative page_summary that synthesizes cross-section trends, source coverage, notable gaps, and why today's items matter.",
            "Use candidates_by_section as the primary evidence; do not invent papers, URLs, authors, scores, or sources.",
            "If a section has fewer than five credible candidates, use the Codex app's own web/search capability to supplement from public sources, and mark candidate_id as manual:<stable-slug>.",
            "Every manual supplement must include real title, URL, and citations from the pages you inspected.",
            "Each section should include exactly five cards when at least five eligible candidates exist.",
            "Trend summaries may mention more than five items, but every concrete claim should be grounded in candidate evidence.",
            "Prioritize a blend of paper quality, discussion heat, recommender-system relevance, and practical tool/product value.",
            "For LLM, data-centric AI, and tools, explicitly explain potential implications for recommender systems.",
        ],
    }


def _aliases(entries: List[Dict[str, Any]]) -> Iterable[str]:
    for entry in entries:
        for field in ("name", "group", "institution"):
            value = entry.get(field)
            if value:
                yield str(value)
        for alias in entry.get("aliases", []):
            yield str(alias)


def _merge_evidence(left: List[Dict[str, str]], right: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output: List[Dict[str, str]] = []
    for entry in left + right:
        key = (entry.get("label", ""), entry.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        output.append(entry)
    return output


def _merge_metrics(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, (int, float)) and isinstance(merged.get(key), (int, float)):
            merged[key] = max(merged[key], value)
        elif key not in merged or merged[key] in (None, ""):
            merged[key] = value
    return merged
