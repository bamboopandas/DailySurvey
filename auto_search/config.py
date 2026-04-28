from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DEFAULT_RUNS_DIR = ROOT / "runs"
DEFAULT_STATE_DIR = ROOT / "state"
DEFAULT_DOCS_DIR = ROOT / "docs"


def load_dotenv(path: Optional[Path] = None) -> None:
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def load_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    for name in ("sources", "people", "keywords"):
        path = CONFIG_DIR / f"{name}.json"
        config[name] = read_json(path) if path.exists() else {}
    return config


def run_dir_for(date_text: str, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    return runs_dir / date_text
