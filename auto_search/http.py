from __future__ import annotations

import datetime as dt
import hashlib
import json
import signal
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any, Dict, Iterator, Optional


USER_AGENT = "auto-search/0.1 (+https://github.com/) research-brief-bot"


class FetchError(RuntimeError):
    pass


class _HardTimeout(TimeoutError):
    pass


@contextmanager
def _request_deadline(timeout: int) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    deadline = max(float(timeout) + 5.0, 1.0)

    def _handle_timeout(signum: int, frame: Optional[FrameType]) -> None:
        raise _HardTimeout(f"request exceeded {deadline:.1f}s deadline")

    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, deadline)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def request_text(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    retries: int = 1,
) -> str:
    merged_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        merged_headers.update(headers)
    last_error: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=merged_headers)
            with _request_deadline(timeout):
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError, _HardTimeout) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"failed to fetch {url}: {last_error}")


def request_text_cached(
    url: str,
    *,
    cache_dir: Path,
    cache_ttl_seconds: int = 0,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    retries: int = 1,
) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.txt"
    if cache_ttl_seconds > 0 and cache_path.exists():
        age = dt.datetime.now().timestamp() - cache_path.stat().st_mtime
        if age <= cache_ttl_seconds:
            return cache_path.read_text(encoding="utf-8")
    try:
        text = request_text(url, headers=headers, timeout=timeout, retries=retries)
    except Exception:
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        raise
    cache_path.write_text(text, encoding="utf-8")
    return text


def request_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    retries: int = 1,
) -> Dict[str, Any]:
    text = request_text(url, headers=headers, timeout=timeout, retries=retries)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"failed to parse JSON from {url}: {exc}") from exc


def request_json_cached(
    url: str,
    *,
    cache_dir: Path,
    cache_ttl_seconds: int = 0,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    retries: int = 1,
) -> Dict[str, Any]:
    text = request_text_cached(
        url,
        cache_dir=cache_dir,
        cache_ttl_seconds=cache_ttl_seconds,
        headers=headers,
        timeout=timeout,
        retries=retries,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"failed to parse cached JSON from {url}: {exc}") from exc
