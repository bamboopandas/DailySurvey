from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List, Tuple

from .. import http
from ..schema import candidate, parse_datetime


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    headers: Dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for query_config in source.get("queries") or []:
        query = query_config["query"]
        params = urllib.parse.urlencode(
            {
                "q": query,
                "sort": query_config.get("sort", "updated"),
                "order": "desc",
                "per_page": int(query_config.get("per_page", source.get("per_page", 20))),
            }
        )
        url = f"https://api.github.com/search/repositories?{params}"
        try:
            data = http.request_json_cached(
                url,
                cache_dir=context["cache_dir"] / "github",
                cache_ttl_seconds=int(source.get("cache_ttl_seconds", 60 * 60)),
                headers=headers,
                retries=1,
            )
            for repo in data.get("items", []):
                updated_at = parse_datetime(repo.get("pushed_at") or repo.get("updated_at"))
                if updated_at and updated_at < lookback_start:
                    continue
                html_url = repo.get("html_url") or ""
                items.append(
                    candidate(
                        title=repo.get("full_name") or repo.get("name") or "",
                        url=html_url,
                        source=source.get("name", "github"),
                        source_type="tool",
                        section_hint=query_config.get("section_hint") or source.get("section_hint"),
                        published_at=repo.get("created_at"),
                        updated_at=repo.get("pushed_at") or repo.get("updated_at"),
                        authors=[repo.get("owner", {}).get("login", "")],
                        summary=repo.get("description") or "",
                        tags=[repo.get("language") or "", "github"],
                        external_ids={"github_repo": repo.get("full_name", "")},
                        metrics={
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "watchers": repo.get("watchers_count", 0),
                        },
                        evidence=[{"label": "GitHub", "url": html_url}],
                        raw={"license": repo.get("license", {})},
                    )
                )
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"github query failed ({query}): {exc}")
    return items, warnings
