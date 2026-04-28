from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from .. import http
from ..schema import candidate, parse_datetime


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def parse_arxiv_feed(xml_text: str, source_name: str, section_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: List[Dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        title = _text(entry, f"{ATOM}title")
        url = _entry_url(entry)
        authors = [_text(author, f"{ATOM}name") for author in entry.findall(f"{ATOM}author")]
        published_at = _text(entry, f"{ATOM}published")
        updated_at = _text(entry, f"{ATOM}updated")
        arxiv_id = _text(entry, f"{ATOM}id").rsplit("/", 1)[-1]
        categories = [
            category.attrib.get("term", "")
            for category in entry.findall(f"{ATOM}category")
            if category.attrib.get("term")
        ]
        comment = _text(entry, f"{ARXIV}comment")
        summary = _text(entry, f"{ATOM}summary")
        if comment:
            summary = f"{summary} Comment: {comment}"
        items.append(
            candidate(
                title=title,
                url=url,
                source=source_name,
                source_type="paper",
                section_hint=section_hint,
                published_at=published_at,
                updated_at=updated_at,
                authors=authors,
                summary=summary,
                tags=categories,
                external_ids={"arxiv": arxiv_id} if arxiv_id else {},
                evidence=[{"label": "arXiv", "url": url}],
            )
        )
    return items


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    max_results = int(source.get("max_results", 50))
    delay_seconds = float(source.get("delay_seconds", 0))
    queries = source.get("queries") or []
    for index, query_config in enumerate(queries):
        query = query_config["search_query"]
        params = urllib.parse.urlencode(
            {
                "search_query": query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        url = f"https://export.arxiv.org/api/query?{params}"
        try:
            parsed = parse_arxiv_feed(
                http.request_text_cached(
                    url,
                    cache_dir=context["cache_dir"] / "arxiv",
                    cache_ttl_seconds=int(source.get("cache_ttl_seconds", 6 * 60 * 60)),
                    retries=1,
                ),
                source.get("name", "arxiv"),
                query_config.get("section_hint"),
            )
            for item in parsed:
                published = parse_datetime(item.get("published_at") or item.get("updated_at"))
                if not published or published >= lookback_start:
                    items.append(item)
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"arxiv query failed ({query_config.get('name', query)}): {exc}")
        if delay_seconds and index < len(queries) - 1:
            time.sleep(delay_seconds)
    return items, warnings


def _text(element: ET.Element, path: str) -> str:
    found = element.find(path)
    if found is None or found.text is None:
        return ""
    return " ".join(found.text.split())


def _entry_url(entry: ET.Element) -> str:
    for link in entry.findall(f"{ATOM}link"):
        if link.attrib.get("rel") == "alternate" and link.attrib.get("href"):
            return link.attrib["href"]
    entry_id = _text(entry, f"{ATOM}id")
    return entry_id
