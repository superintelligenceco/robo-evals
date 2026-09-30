"""Command-line interface: ``robo-evals run|list|compare|serve``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from robo_evals import __version__
from robo_evals.policy import close_policy, load_policy
from robo_evals.randomization import PRESETS, get_preset
from robo_evals.report import compare_markdown, load_report, to_markdown, write_reports
from robo_evals.runner import VIDEO_MODES, EpisodeResult, evaluate
from robo_evals.tasks import SUITES, TASKS
from robo_evals.video import VIDEO_FORMATS


def _default_name(spec: str) -> str:
    tail = spec.rstrip("/").rsplit("/", 1)[-1]
    return tail.replace(":", ".").replace(".py", "") or "policy"


def cmd_run(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    name = args.name or _default_name(args.policy)
    out = Path(args.out) / name
    tasks = [t.strip() for t in args.tasks.split(",")] if args.tasks else None

    def progress(ep: EpisodeResult) -> None:
        if not args.quiet:
            mark = "ok  " if ep.success else "fail"
            print(f"  {ep.task:<11} ep {ep.episode:>3}  {mark}  steps={ep.steps}", file=sys.stderr)

    try:
        result = evaluate(
            policy,
            suite=args.suite,
            tasks=tasks,
            episodes=args.episodes,
            seed=args.seed,
            randomization=get_preset(args.randomization),
            max_steps=args.max_steps,
            policy_name=name,
            video=args.video,
            video_dir=out / "videos",
            video_format=args.video_format,
            image_obs=args.image_obs,
            progress=progress,
        )
    finally:
        close_policy(policy)
    json_path, md_path = write_reports(result, out)
    print(to_markdown(result))
    print(f"Wrote {json_path} and {md_path}", file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("Tasks:")
    for name, cls in TASKS.items():
        print(f"  {name:<11} max_steps={cls.max_steps:<4} {cls.instruction}")
    print("Suites:")
    for suite, names in SUITES.items():
        print(f"  {suite:<11} {', '.join(names)}")
    print("Randomization presets:")
    for preset, value in PRESETS.items():
        print(f"  {preset:<11} {value.to_dict()}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    table = compare_markdown([load_report(p) for p in args.reports])
    if args.out:
        Path(args.out).write_text(table, encoding="utf-8")
    print(table, end="")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from robo_evals.remote import make_http_server, serve_websocket

    policy = load_policy(args.policy)
    name = args.name or _default_name(args.policy)
    if args.protocol == "ws":
        server = serve_websocket(policy, args.host, args.port, name)
        print(f"Serving {name} on ws://{args.host}:{args.port}", file=sys.stderr)
    else:
        server = make_http_server(policy, args.host, args.port, name)
        print(f"Serving {name} on http://{args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="robo-evals", description="Evaluate robot manipulation policies in MuJoCo."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="evaluate a policy on a task suite")
    run.add_argument("--policy", required=True, help="random | scripted | module:attr | URL")
    run.add_argument("--suite", default="core", choices=sorted(SUITES))
    run.add_argument("--tasks", help="comma-separated task names; overrides --suite")
    run.add_argument("--episodes", type=int, default=10, help="episodes per task")
    run.add_argument("--seed", type=int, default=0, help="base seed")
    run.add_argument("--randomization", default="default", choices=sorted(PRESETS))
    run.add_argument("--max-steps", type=int, help="override each task's step limit")
    run.add_argument("--video", default="none", choices=VIDEO_MODES)
    run.add_argument("--video-format", default="gif", choices=VIDEO_FORMATS)
    run.add_argument("--image-obs", action="store_true", help="add camera images to observations")
    run.add_argument("--out", default="results", help="output directory")
    run.add_argument("--name", help="policy name in reports (default: derived from --policy)")
    run.add_argument("-q", "--quiet", action="store_true", help="hide per-episode progress")
    run.set_defaults(func=cmd_run)

    lst = sub.add_parser("list", help="list tasks, suites, and randomization presets")
    lst.set_defaults(func=cmd_list)

    cmp = sub.add_parser("compare", help="compare report.json files side by side")
    cmp.add_argument("reports", nargs="+")
    cmp.add_argument("--out", help="also write the table to this file")
    cmp.set_defaults(func=cmd_compare)

    srv = sub.add_parser("serve", help="serve a policy over HTTP or WebSocket")
    srv.add_argument("--policy", required=True)
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--protocol", default="http", choices=("http", "ws"))
    srv.add_argument("--name")
    srv.set_defaults(func=cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, TypeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
