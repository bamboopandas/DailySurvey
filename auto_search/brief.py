from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .config import read_json, write_json
from .schema import SECTIONS


def scaffold_brief(candidates_path: Path, output_path: Path) -> Dict[str, Any]:
    data = read_json(candidates_path)
    brief = {
        "date": data.get("date"),
        "title": "每日 AI / 推荐系统情报简报",
        "_fallback_brief": True,
        "page_summary": fallback_page_summary(data),
        "sections": [],
    }
    by_section = data.get("candidates_by_section") or {}
    for section_id, title in SECTIONS.items():
        candidates = by_section.get(section_id, [])[:5]
        brief["sections"].append(
            {
                "id": section_id,
                "title": title,
                "trend_summary": fallback_trend(title, candidates),
                "trend_bullets": fallback_bullets(candidates),
                "cards": [fallback_card(item) for item in candidates],
            }
        )
    write_json(output_path, brief)
    return brief


def fallback_trend(title: str, candidates: List[Dict[str, Any]]) -> str:
    if not candidates:
        return f"{title} 在本次抓取窗口内没有足够候选。"
    sources = sorted({item.get("source", "") for item in candidates if item.get("source")})
    return f"{title} 本次抓取到 {len(candidates)} 条高分候选，主要来自 {', '.join(sources[:5])}。这是 dry-run 兜底简报，只用于验证管道；正式日报会由 Codex gpt-5.5 基于这些候选和必要的本 app 搜索补充生成趋势判断。"


def fallback_bullets(candidates: List[Dict[str, Any]]) -> List[str]:
    bullets = []
    for item in candidates[:3]:
        bullets.append(f"{item.get('title', '')}（{item.get('source', '')}）")
    return bullets


def fallback_card(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_id": item.get("id"),
        "title": item.get("title"),
        "summary_cn": item.get("summary") or "候选信息已采集，等待 Codex gpt-5.5 生成中文摘要。",
        "why_it_matters": "该条目在关键词、来源质量或热度指标上获得较高粗评分。",
        "recsys_inspiration": "正式简报会补充它对推荐系统研究的潜在启发。",
        "url": item.get("url"),
        "citations": item.get("evidence", []),
    }


def fallback_page_summary(data: Dict[str, Any]) -> str:
    counts = data.get("counts", {})
    by_section = data.get("candidates_by_section") or {}
    section_counts = {section_id: len(items) for section_id, items in by_section.items()}
    warnings = data.get("warnings") or []
    return (
        "这是 dry-run 兜底简报，只用于验证采集、渲染和飞书推送链路；正式日报应由 Codex gpt-5.5 在自动化任务中生成。"
        f"本次采集原始候选 {counts.get('raw', 0)} 条，去重后 {counts.get('deduped', 0)} 条，"
        f"各板块候选数量为 {section_counts}。"
        f"采集警告 {len(warnings)} 条；如某板块候选不足，正式自动化会使用本 app 内置搜索/浏览能力补充公开来源。"
    )
