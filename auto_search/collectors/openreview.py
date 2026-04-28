from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Tuple

from .. import http
from ..schema import candidate, parse_datetime


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    limit = int(source.get("limit", 25))
    for query_config in source.get("queries") or []:
        params = {
            "term": query_config["term"],
            "content": query_config.get("content", "all"),
            "source": "forum",
            "sort": "tmdate:desc",
            "limit": limit,
        }
        if query_config.get("venueid"):
            params["venueid"] = query_config["venueid"]
        url = f"https://api2.openreview.net/notes/search?{urllib.parse.urlencode(params)}"
        try:
            data = http.request_json_cached(
                url,
                cache_dir=context["cache_dir"] / "openreview",
                cache_ttl_seconds=int(source.get("cache_ttl_seconds", 6 * 60 * 60)),
                retries=1,
            )
            for note in data.get("notes", []):
                item = _note_to_candidate(note, source, query_config)
                updated_at = parse_datetime(item.get("updated_at") or item.get("published_at"))
                if not updated_at or updated_at >= lookback_start:
                    items.append(item)
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"openreview query failed ({query_config.get('term')}): {exc}")
    return items, warnings


def _note_to_candidate(note: Dict[str, Any], source: Dict[str, Any], query_config: Dict[str, Any]) -> Dict[str, Any]:
    content = note.get("content") or {}
    title = _value(content.get("title"))
    abstract = _value(content.get("abstract"))
    authors = _value(content.get("authors"))
    if isinstance(authors, str):
        authors_list = [part.strip() for part in authors.split(",") if part.strip()]
    else:
        authors_list = list(authors or [])
    note_id = note.get("id") or note.get("forum") or ""
    url = f"https://openreview.net/forum?id={note.get('forum') or note_id}"
    venue = _value(content.get("venue")) or _value(content.get("venueid")) or query_config.get("venueid", "")
    tags = [tag for tag in [venue, "openreview"] if tag]
    return candidate(
        title=title,
        url=url,
        source=source.get("name", "openreview"),
        source_type="paper",
        section_hint=query_config.get("section_hint") or source.get("section_hint"),
        published_at=note.get("tcdate"),
        updated_at=note.get("tmdate"),
        authors=authors_list,
        summary=abstract,
        tags=tags,
        external_ids={"openreview": note_id} if note_id else {},
        evidence=[{"label": "OpenReview", "url": url}],
    )


def _value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value
