from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List


def publish_pages(docs_dir: Path, message: str, dry_run: bool = False) -> Dict[str, object]:
    if not is_git_repo():
        return {"published": False, "reason": "not a git repository"}
    if not has_remote():
        return {"published": False, "reason": "no git remote configured"}
    changed = changed_docs(docs_dir)
    if not changed:
        return {"published": False, "reason": "no docs changes"}
    commands = [
        ["git", "add", str(docs_dir)],
        ["git", "commit", "-m", message],
        push_command(),
    ]
    if dry_run:
        return {"published": False, "dry_run": True, "commands": commands, "changed": changed}
    outputs = []
    for command in commands:
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        outputs.append({"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
        if completed.returncode != 0:
            if command[:2] == ["git", "commit"] and "nothing to commit" in completed.stdout + completed.stderr:
                return {"published": False, "reason": "nothing to commit", "outputs": outputs}
            raise RuntimeError(f"command failed: {' '.join(command)}\n{completed.stderr or completed.stdout}")
    return {"published": True, "outputs": outputs}


def is_git_repo() -> bool:
    completed = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=False, text=True, capture_output=True)
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def has_remote() -> bool:
    completed = subprocess.run(["git", "remote"], check=False, text=True, capture_output=True)
    return completed.returncode == 0 and bool(completed.stdout.strip())


def push_command() -> List[str]:
    completed = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode == 0:
        return ["git", "push"]
    branch = subprocess.run(["git", "branch", "--show-current"], check=False, text=True, capture_output=True)
    branch_name = branch.stdout.strip() or "main"
    return ["git", "push", "-u", "origin", branch_name]


def changed_docs(docs_dir: Path) -> List[str]:
    completed = subprocess.run(["git", "status", "--short", str(docs_dir)], check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
