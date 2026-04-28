from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any, Dict, Optional

from .brief import scaffold_brief
from .config import DEFAULT_DOCS_DIR, DEFAULT_RUNS_DIR, DEFAULT_STATE_DIR, load_dotenv, read_json
from .feishu import send_card, send_text
from .pipeline import candidates_by_id, collect_candidates, mark_seen_from_brief
from .publish import publish_pages
from .render import render_outputs


def main(argv: Optional[list] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="auto_search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="collect candidate items")
    collect_parser.add_argument("--lookback-hours", type=int, default=48)
    collect_parser.add_argument("--output", type=Path)
    collect_parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    collect_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    collect_parser.add_argument("--include-seen", action="store_true")

    scaffold_parser = subparsers.add_parser("scaffold-brief", help="create a fallback brief for dry-run")
    scaffold_parser.add_argument("candidates", type=Path)
    scaffold_parser.add_argument("--output", type=Path)

    render_parser = subparsers.add_parser("render", help="render HTML report and Feishu card")
    render_parser.add_argument("brief", type=Path)
    render_parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)

    send_parser = subparsers.add_parser("send-feishu", help="send Feishu interactive card")
    send_parser.add_argument("card", type=Path)
    send_parser.add_argument("--brief", type=Path)
    send_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    send_parser.add_argument("--no-mark-seen", action="store_true")
    send_parser.add_argument("--allow-fallback", action="store_true")

    failure_parser = subparsers.add_parser("send-failure", help="send a Feishu failure text message")
    failure_parser.add_argument("message")

    publish_parser = subparsers.add_parser("publish-pages", help="commit and push generated GitHub Pages docs")
    publish_parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    publish_parser.add_argument("--message", default=None)
    publish_parser.add_argument("--dry-run", action="store_true")

    run_parser = subparsers.add_parser("run", help="collect, scaffold brief, render, optionally send")
    run_parser.add_argument("--lookback-hours", type=int, default=48)
    run_parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    run_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    run_parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    run_parser.add_argument("--send-feishu", action="store_true")
    run_parser.add_argument("--include-seen", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "collect":
        output = args.output or default_run_dir(args.runs_dir) / "candidates.json"
        result = collect_candidates(
            lookback_hours=args.lookback_hours,
            output_path=output,
            state_dir=args.state_dir,
            include_seen=args.include_seen,
        )
        print(f"wrote {output} ({result['counts']['after_seen_filter']} candidates)")
        for warning in result.get("warnings", []):
            print(f"warning: {warning}")
        return 0

    if args.command == "scaffold-brief":
        output = args.output or args.candidates.parent / "brief.json"
        scaffold_brief(args.candidates, output)
        print(f"wrote {output}")
        return 0

    if args.command == "render":
        outputs = render_outputs(args.brief, docs_dir=args.docs_dir)
        for name, path in outputs.items():
            print(f"wrote {name}: {path}")
        return 0

    if args.command == "send-feishu":
        if args.brief and not args.allow_fallback:
            brief = read_json(args.brief)
            if brief.get("_fallback_brief"):
                raise RuntimeError("refusing to send fallback brief; generate a Codex gpt-5.5 brief.json or pass --allow-fallback for a pipeline test")
        response = send_card(args.card)
        print(response)
        if args.brief and not args.no_mark_seen:
            candidates = candidates_by_id(args.brief.parent / "candidates.json")
            mark_seen_from_brief(read_json(args.brief), candidates, args.state_dir)
            print(f"updated {args.state_dir / 'seen.json'}")
        return 0

    if args.command == "send-failure":
        response = send_text(args.message)
        print(response)
        return 0

    if args.command == "publish-pages":
        message = args.message or f"Update daily brief {dt.datetime.now().strftime('%Y-%m-%d')}"
        result = publish_pages(args.docs_dir, message, dry_run=args.dry_run)
        print(result)
        return 0

    if args.command == "run":
        run_dir = default_run_dir(args.runs_dir)
        candidates_path = run_dir / "candidates.json"
        brief_path = run_dir / "brief.json"
        collect_candidates(
            lookback_hours=args.lookback_hours,
            output_path=candidates_path,
            state_dir=args.state_dir,
            include_seen=args.include_seen,
        )
        scaffold_brief(candidates_path, brief_path)
        outputs = render_outputs(brief_path, docs_dir=args.docs_dir)
        if args.send_feishu:
            response = send_card(outputs["card"])
            print(response)
            candidates = candidates_by_id(candidates_path)
            mark_seen_from_brief(read_json(brief_path), candidates, args.state_dir)
        print(f"run_dir={run_dir}")
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


def default_run_dir(runs_dir: Path) -> Path:
    date_text = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    path = runs_dir / date_text
    path.mkdir(parents=True, exist_ok=True)
    return path
