from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any, Dict, List, Tuple

from .. import http
from ..schema import candidate


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    timestamp = int(lookback_start.timestamp())
    for query_config in source.get("queries") or []:
        params = urllib.parse.urlencode(
            {
                "query": query_config["query"],
                "tags": query_config.get("tags", "story"),
                "hitsPerPage": int(query_config.get("hits_per_page", source.get("hits_per_page", 20))),
                "numericFilters": f"created_at_i>{timestamp}",
            }
        )
        url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"
        try:
            data = http.request_json_cached(
                url,
                cache_dir=context["cache_dir"] / "hackernews",
                cache_ttl_seconds=int(source.get("cache_ttl_seconds", 30 * 60)),
                retries=1,
            )
            for hit in data.get("hits", []):
                title = hit.get("title") or hit.get("story_title") or ""
                target_url = hit.get("url") or _hn_item_url(hit)
                created_at = hit.get("created_at")
                points = hit.get("points") or 0
                comments = hit.get("num_comments") or 0
                items.append(
                    candidate(
                        title=title,
                        url=target_url,
                        source=source.get("name", "hackernews"),
                        source_type="social",
                        section_hint=query_config.get("section_hint") or source.get("section_hint", "ai_social_tools"),
                        published_at=created_at,
                        updated_at=created_at,
                        authors=[hit.get("author", "")],
                        summary=f"Hacker News discussion with {points} points and {comments} comments.",
                        tags=["hacker news", query_config["query"]],
                        external_ids={"hn_object_id": str(hit.get("objectID") or "")},
                        metrics={"points": points, "comments": comments},
                        evidence=[{"label": "Hacker News", "url": _hn_item_url(hit)}],
                        raw={"target_url": target_url},
                    )
                )
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"hackernews query failed ({query_config.get('query')}): {exc}")
    return items, warnings


def _hn_item_url(hit: Dict[str, Any]) -> str:
    object_id = hit.get("objectID") or hit.get("story_id") or ""
    return f"https://news.ycombinator.com/item?id={object_id}" if object_id else "https://news.ycombinator.com/"
