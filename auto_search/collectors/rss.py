from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from .. import http
from ..schema import candidate, parse_datetime


ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(xml_text: str, source_name: str, source_type: str, section_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    if root.tag.endswith("rss"):
        return _parse_rss(root, source_name, source_type, section_hint)
    return _parse_atom(root, source_name, source_type, section_hint)


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    lookback_start = context["lookback_start"]
    for feed in source.get("feeds") or []:
        try:
            parsed = parse_feed(
                http.request_text_cached(
                    feed["url"],
                    cache_dir=context["cache_dir"] / "rss",
                    cache_ttl_seconds=int(feed.get("cache_ttl_seconds", source.get("cache_ttl_seconds", 60 * 60))),
                    retries=1,
                ),
                feed.get("name") or source.get("name", "rss"),
                feed.get("source_type", source.get("source_type", "blog")),
                feed.get("section_hint") or source.get("section_hint"),
            )
            for item in parsed:
                published = parse_datetime(item.get("published_at") or item.get("updated_at"))
                if not published or published >= lookback_start:
                    items.append(item)
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"feed failed ({feed.get('name', feed.get('url'))}): {exc}")
    return items, warnings


def _parse_rss(root: ET.Element, source_name: str, source_type: str, section_hint: Optional[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in root.findall("./channel/item"):
        title = _child_text(entry, "title")
        url = _child_text(entry, "link") or _child_text(entry, "guid")
        authors = [_child_text(entry, "author")]
        categories = [category.text or "" for category in entry.findall("category")]
        items.append(
            candidate(
                title=title,
                url=url,
                source=source_name,
                source_type=source_type,
                section_hint=section_hint,
                published_at=_child_text(entry, "pubDate"),
                updated_at=_child_text(entry, "updated"),
                authors=authors,
                summary=_child_text(entry, "description"),
                tags=categories,
                evidence=[{"label": source_name, "url": url}],
            )
        )
    return items


def _parse_atom(root: ET.Element, source_name: str, source_type: str, section_hint: Optional[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.attrib.get("href") and link.attrib.get("rel", "alternate") == "alternate":
                url = link.attrib["href"]
                break
        authors = [_child_text(author, f"{ATOM}name") for author in entry.findall(f"{ATOM}author")]
        items.append(
            candidate(
                title=_child_text(entry, f"{ATOM}title"),
                url=url or _child_text(entry, f"{ATOM}id"),
                source=source_name,
                source_type=source_type,
                section_hint=section_hint,
                published_at=_child_text(entry, f"{ATOM}published"),
                updated_at=_child_text(entry, f"{ATOM}updated"),
                authors=authors,
                summary=_child_text(entry, f"{ATOM}summary") or _child_text(entry, f"{ATOM}content"),
                evidence=[{"label": source_name, "url": url or _child_text(entry, f"{ATOM}id")}],
            )
        )
    return items


def _child_text(element: ET.Element, path: str) -> str:
    child = element.find(path)
    if child is None or child.text is None:
        return ""
    return " ".join(child.text.split())
