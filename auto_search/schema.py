from __future__ import annotations

import datetime as dt
import hashlib
import re
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional


UTC = dt.timezone.utc

SECTIONS = {
    "recsys_research": "推荐系统研究动态",
    "llm_hotspots": "LLM 热点论文",
    "data_centric_ai": "Data-centric AI",
    "ai_social_tools": "AI 社媒/工具/产品动态",
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def parse_datetime(value: Any) -> Optional[dt.datetime]:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = dt.datetime.fromtimestamp(normalize_timestamp(float(value)), tz=UTC)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            number = float(text)
            if 1000 <= number <= 3000:
                return dt.datetime(int(number), 1, 1, tzinfo=UTC)
            return dt.datetime.fromtimestamp(normalize_timestamp(number), tz=UTC)
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError, IndexError, OverflowError):
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_timestamp(value: float) -> float:
    while value > 10_000_000_000:
        value = value / 1000
    return value


def isoformat(value: Any) -> Optional[str]:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def stable_hash(parts: Iterable[str], prefix: str = "item") -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update((part or "").encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return f"{prefix}:{digest.hexdigest()[:16]}"


def text_blob(item: Dict[str, Any]) -> str:
    chunks: List[str] = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        " ".join(item.get("authors") or []),
        " ".join(item.get("tags") or []),
        str(item.get("source") or ""),
    ]
    return normalize_key(" ".join(chunks))


def candidate_id(item: Dict[str, Any]) -> str:
    if item.get("id"):
        return str(item["id"])
    return stable_hash([item.get("url") or "", item.get("title") or ""], prefix="candidate")


def dedupe_key(item: Dict[str, Any]) -> str:
    external_ids = item.get("external_ids") or {}
    for key in ("arxiv", "doi", "semantic_scholar"):
        value = external_ids.get(key)
        if value:
            return f"{key}:{normalize_key(str(value))}"
    title = normalize_key(str(item.get("title") or ""))
    if title:
        return f"title:{title}"
    return f"url:{normalize_key(str(item.get('url') or candidate_id(item)))}"


def candidate(
    *,
    title: str,
    url: str,
    source: str,
    source_type: str,
    section_hint: Optional[str] = None,
    published_at: Any = None,
    updated_at: Any = None,
    authors: Optional[List[str]] = None,
    summary: str = "",
    tags: Optional[List[str]] = None,
    external_ids: Optional[Dict[str, str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    evidence: Optional[List[Dict[str, str]]] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    clean_title = normalize_text(title)
    clean_url = normalize_text(url)
    item = {
        "id": stable_hash([source, clean_url, clean_title], prefix=source),
        "title": clean_title,
        "url": clean_url,
        "source": source,
        "source_type": source_type,
        "section_hint": section_hint,
        "published_at": isoformat(published_at),
        "updated_at": isoformat(updated_at),
        "authors": [normalize_text(a) for a in (authors or []) if normalize_text(a)],
        "summary": normalize_text(summary),
        "tags": [normalize_text(t) for t in (tags or []) if normalize_text(t)],
        "external_ids": external_ids or {},
        "metrics": metrics or {},
        "evidence": evidence or [{"label": source, "url": clean_url}],
        "raw": raw or {},
    }
    item["dedupe_key"] = dedupe_key(item)
    return item
