from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List, Tuple

from .. import http
from ..schema import candidate, parse_datetime


FIELDS = "title,abstract,authors,url,year,publicationDate,citationCount,externalIds,venue,fieldsOfStudy"


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    headers: Dict[str, str] = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if source.get("requires_api_key") and not api_key:
        return [], ["semantic scholar skipped: SEMANTIC_SCHOLAR_API_KEY is not configured"]
    if api_key:
        headers["x-api-key"] = api_key
    for query_config in source.get("queries") or []:
        params = urllib.parse.urlencode(
            {
                "query": query_config["query"],
                "limit": int(query_config.get("limit", source.get("limit", 20))),
                "fields": FIELDS,
            }
        )
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
        try:
            data = http.request_json_cached(
                url,
                cache_dir=context["cache_dir"] / "semantic_scholar",
                cache_ttl_seconds=int(source.get("cache_ttl_seconds", 6 * 60 * 60)),
                headers=headers,
                retries=1,
            )
            for paper in data.get("data", []):
                published_at = parse_datetime(paper.get("publicationDate"))
                if published_at and published_at < lookback_start:
                    continue
                external_ids = paper.get("externalIds") or {}
                semantic_id = paper.get("paperId") or ""
                url_value = paper.get("url") or (f"https://www.semanticscholar.org/paper/{semantic_id}" if semantic_id else "")
                items.append(
                    candidate(
                        title=paper.get("title") or "",
                        url=url_value,
                        source=source.get("name", "semantic_scholar"),
                        source_type="paper",
                        section_hint=query_config.get("section_hint") or source.get("section_hint"),
                        published_at=paper.get("publicationDate") or paper.get("year"),
                        authors=[author.get("name", "") for author in paper.get("authors", [])],
                        summary=paper.get("abstract") or "",
                        tags=[paper.get("venue") or ""] + list(paper.get("fieldsOfStudy") or []),
                        external_ids={
                            "semantic_scholar": semantic_id,
                            "doi": external_ids.get("DOI", ""),
                            "arxiv": external_ids.get("ArXiv", ""),
                        },
                        metrics={"citations": paper.get("citationCount", 0)},
                        evidence=[{"label": "Semantic Scholar", "url": url_value}],
                    )
                )
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"semantic scholar query failed ({query_config.get('query')}): {exc}")
    return items, warnings
