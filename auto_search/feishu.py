from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from .config import read_json


def send_card(card_path: Path, webhook: Optional[str] = None, sign_secret: Optional[str] = None) -> Dict[str, Any]:
    webhook = webhook or os.environ.get("FEISHU_BOT_WEBHOOK")
    if not webhook:
        raise RuntimeError("FEISHU_BOT_WEBHOOK is required")
    sign_secret = sign_secret or os.environ.get("FEISHU_BOT_SIGN_SECRET")
    payload = read_json(card_path)
    if sign_secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = sign(timestamp, sign_secret)
    return post_payload(payload, webhook, sign_secret=None)


def send_text(message: str, webhook: Optional[str] = None, sign_secret: Optional[str] = None) -> Dict[str, Any]:
    webhook = webhook or os.environ.get("FEISHU_BOT_WEBHOOK")
    if not webhook:
        raise RuntimeError("FEISHU_BOT_WEBHOOK is required")
    sign_secret = sign_secret or os.environ.get("FEISHU_BOT_SIGN_SECRET")
    payload: Dict[str, Any] = {"msg_type": "text", "content": {"text": message}}
    return post_payload(payload, webhook, sign_secret)


def post_payload(payload: Dict[str, Any], webhook: str, sign_secret: Optional[str] = None) -> Dict[str, Any]:
    if sign_secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = sign(timestamp, sign_secret)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")
