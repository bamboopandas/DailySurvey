from __future__ import annotations

import html.parser
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from .. import http
from ..schema import candidate


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Dict[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        attr_map = {name: value or "" for name, value in attrs}
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href:
            text = " ".join(" ".join(self._current_text).split())
            if text:
                self.links.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._current_text = []


def collect(source: Dict[str, Any], context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    max_links = int(source.get("max_links", 25))
    for page in source.get("pages") or []:
        try:
            text = http.request_text_cached(
                page["url"],
                cache_dir=context["cache_dir"] / "webpage",
                cache_ttl_seconds=int(page.get("cache_ttl_seconds", source.get("cache_ttl_seconds", 60 * 60))),
                retries=1,
            )
            parser = LinkParser()
            parser.feed(text)
            for link in parser.links[:max_links]:
                url = urllib.parse.urljoin(page["url"], link["href"])
                title = link["text"]
                items.append(
                    candidate(
                        title=title,
                        url=url,
                        source=page.get("name") or source.get("name", "webpage"),
                        source_type=page.get("source_type", source.get("source_type", "web")),
                        section_hint=page.get("section_hint") or source.get("section_hint"),
                        summary="",
                        tags=page.get("tags", []),
                        evidence=[{"label": page.get("name") or source.get("name", "webpage"), "url": url}],
                    )
                )
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            warnings.append(f"webpage failed ({page.get('name', page.get('url'))}): {exc}")
    return items, warnings
