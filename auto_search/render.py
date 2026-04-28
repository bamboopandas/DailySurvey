from __future__ import annotations

import datetime as dt
import html
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import DEFAULT_DOCS_DIR, read_json, write_json
from .pipeline import candidates_by_id
from .schema import SECTIONS


def render_outputs(brief_path: Path, docs_dir: Path = DEFAULT_DOCS_DIR) -> Dict[str, Path]:
    brief = read_json(brief_path)
    run_dir = brief_path.parent
    candidates_path = run_dir / "candidates.json"
    candidates = candidates_by_id(candidates_path) if candidates_path.exists() else {}
    normalized = normalize_brief(brief, candidates)
    write_json(brief_path, normalized)

    date_text = normalized.get("date") or dt.datetime.now().strftime("%Y-%m-%d")
    report_type = normalized.get("report_type", "daily")
    report_dir = report_dir_for(docs_dir, date_text, report_type)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "index.html"
    report_path.write_text(render_html(normalized), encoding="utf-8")
    index_path = index_path_for(docs_dir, report_type)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(render_index(normalized), encoding="utf-8")

    report_url = report_public_url(date_text, report_type)
    card = build_feishu_card(normalized, report_url)
    card_path = run_dir / "feishu_card.json"
    write_json(card_path, card)
    return {"report": report_path, "index": index_path, "card": card_path}


def normalize_brief(brief: Dict[str, Any], candidates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    brief = dict(brief)
    brief.setdefault("report_type", "daily")
    brief.setdefault("title", "每日 AI / 推荐系统情报简报")
    brief.setdefault("date", dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d"))
    brief.setdefault("page_summary", "")
    sections = []
    existing_sections = {section.get("id"): section for section in brief.get("sections", [])}
    for section_id, section_title in SECTIONS.items():
        section = dict(existing_sections.get(section_id) or {})
        section.setdefault("id", section_id)
        section.setdefault("title", section_title)
        if "section_summary" not in section and section.get("trend_summary"):
            section["section_summary"] = section.get("trend_summary")
        if "news_bullets" not in section and section.get("trend_bullets"):
            section["news_bullets"] = section.get("trend_bullets")
        section.setdefault("section_summary", "")
        section.setdefault("news_bullets", [])
        section.setdefault("trend_summary", "")
        section.setdefault("trend_bullets", [])
        section["cards"] = [enrich_card(card, candidates) for card in section.get("cards", [])[:5]]
        sections.append(section)
    brief["sections"] = sections
    return brief


def enrich_card(card: Dict[str, Any], candidates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    card = dict(card)
    candidate = candidates.get(card.get("candidate_id", ""))
    if candidate:
        card.setdefault("title", candidate.get("title"))
        card.setdefault("url", candidate.get("url"))
        card.setdefault("source", candidate.get("source"))
        card.setdefault("published_at", candidate.get("published_at"))
        card.setdefault("summary_cn", candidate.get("summary"))
        card.setdefault("citations", candidate.get("evidence") or [{"label": candidate.get("source", "source"), "url": candidate.get("url", "")}])
        card.setdefault("score", candidate.get("score"))
        card.setdefault("authors", candidate.get("authors", []))
    card.setdefault("citations", [])
    card.setdefault("summary_cn", "")
    card.setdefault("why_it_matters", "")
    card.setdefault("recsys_inspiration", "")
    return card


def render_html(brief: Dict[str, Any]) -> str:
    title = html.escape(str(brief.get("title", "每日 AI / 推荐系统情报简报")))
    date_text = html.escape(str(brief.get("date", "")))
    sections_html = "\n".join(render_section(section) for section in brief.get("sections", []))
    summary = paragraphs(brief.get("page_summary", ""))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{title} - {date_text}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #15171a;
      --muted: #5f6875;
      --line: #dfe4ea;
      --accent: #0f766e;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 40px 20px 72px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 28px;
      padding-bottom: 24px;
    }}
    h1 {{
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.18;
      margin: 0 0 8px;
    }}
    .date, .muted {{
      color: var(--muted);
    }}
    section {{
      margin-top: 28px;
      padding-top: 8px;
    }}
    h2 {{
      font-size: 24px;
      margin: 0 0 12px;
    }}
    .trend {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px 20px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
      margin-top: 16px;
    }}
    article {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    h3 {{
      font-size: 17px;
      line-height: 1.35;
      margin: 0 0 10px;
    }}
    a {{
      color: var(--accent);
      text-decoration-thickness: .08em;
      text-underline-offset: .18em;
    }}
    ul {{
      padding-left: 1.2em;
    }}
    .label {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 10px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <div class="date">{date_text}</div>
      {summary}
    </header>
    {sections_html}
  </main>
</body>
</html>
"""


def render_section(section: Dict[str, Any]) -> str:
    title = html.escape(str(section.get("title", "")))
    trend = paragraphs(section_text(section))
    bullets = section.get("news_bullets") or section.get("trend_bullets") or []
    if bullets:
        trend += "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in bullets) + "</ul>"
    cards = "\n".join(render_card(card) for card in section.get("cards", []))
    return f"""<section id="{html.escape(str(section.get("id", "")))}">
  <h2>{title}</h2>
  <div class="trend">{trend}</div>
  <div class="cards">{cards}</div>
</section>"""


def render_card(card: Dict[str, Any]) -> str:
    title = html.escape(str(card.get("title", "")))
    url = html.escape(str(card.get("url", "")), quote=True)
    summary = paragraphs(card.get("summary_cn", ""))
    why = paragraphs(card.get("why_it_matters", ""), label="为什么值得看")
    inspiration = paragraphs(card.get("recsys_inspiration", ""), label="对推荐系统的启发")
    citations = render_citations(card.get("citations", []))
    return f"""<article>
  <h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
  {summary}
  {why}
  {inspiration}
  {citations}
</article>"""


def render_citations(citations: List[Dict[str, str]]) -> str:
    links = []
    for citation in citations:
        url = citation.get("url")
        if not url:
            continue
        label = html.escape(str(citation.get("label") or "source"))
        links.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>')
    if not links:
        return ""
    return f'<div class="label">引用：{" / ".join(links)}</div>'


def paragraphs(value: Any, label: Optional[str] = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    escaped = html.escape(text)
    if label:
        return f"<p><strong>{html.escape(label)}：</strong>{escaped}</p>"
    return "".join(f"<p>{part}</p>" for part in escaped.split("\n") if part.strip())


def render_index(brief: Dict[str, Any]) -> str:
    title = html.escape(str(brief.get("title", "每日 AI / 推荐系统情报简报")))
    date_text = html.escape(str(brief.get("date", "")))
    report_type = brief.get("report_type", "daily")
    href = f"{date_text}/" if report_type == "monthly" else f"reports/{date_text}/"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta http-equiv="refresh" content="0; url={href}">
  <title>{title}</title>
</head>
<body>
  <p><a href="{href}">打开 {date_text} 简报</a></p>
</body>
</html>
"""


def build_feishu_card(brief: Dict[str, Any], report_url: str) -> Dict[str, Any]:
    elements: List[Dict[str, Any]] = []
    report_type = brief.get("report_type", "daily")
    page_summary = truncate_md(str(brief.get("page_summary") or ""), 1100)
    if page_summary:
        elements.append({"tag": "markdown", "content": page_summary})
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "阅读月报" if report_type == "monthly" else "阅读全文"},
                    "url": report_url,
                    "type": "primary",
                }
            ],
        }
    )
    for section in brief.get("sections", []):
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": section_markdown(section)})
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green" if report_type == "monthly" else "blue",
                "title": {"tag": "plain_text", "content": f"{brief.get('title', '每日简报')} · {brief.get('date', '')}"},
            },
            "elements": elements,
        },
    }


def section_markdown(section: Dict[str, Any]) -> str:
    parts = [f"**{section.get('title', '')}**"]
    trend = section_text(section)
    if trend:
        parts.append(truncate_md(trend, 700))
    bullets = section.get("news_bullets") or section.get("trend_bullets") or []
    for bullet in bullets[:4]:
        parts.append(f"- {bullet}")
    for index, card in enumerate(section.get("cards", [])[:5], start=1):
        title = card.get("title", "")
        url = card.get("url", "")
        summary = truncate_md(str(card.get("summary_cn") or ""), 160)
        if url:
            parts.append(f"{index}. [{title}]({url})：{summary}")
        else:
            parts.append(f"{index}. {title}：{summary}")
    return "\n".join(parts)


def truncate_md(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def section_text(section: Dict[str, Any]) -> str:
    return str(section.get("section_summary") or section.get("trend_summary") or "").strip()


def report_dir_for(docs_dir: Path, date_text: str, report_type: str) -> Path:
    if report_type == "monthly":
        return docs_dir / "monthly" / date_text
    return docs_dir / "reports" / date_text


def index_path_for(docs_dir: Path, report_type: str) -> Path:
    if report_type == "monthly":
        return docs_dir / "monthly" / "index.html"
    return docs_dir / "index.html"


def report_public_url(date_text: str, report_type: str = "daily") -> str:
    base_url = os.environ.get("PAGES_BASE_URL", "").rstrip("/")
    default_path = "docs/monthly" if report_type == "monthly" else "docs/reports"
    env_name = "PAGES_MONTHLY_PATH" if report_type == "monthly" else "PAGES_REPORTS_PATH"
    reports_path = os.environ.get(env_name, default_path).strip("/")
    if base_url:
        return f"{base_url}/{reports_path}/{date_text}/"
    return f"{reports_path}/{date_text}/index.html"
