"""OTASEC command line.

  python -m otasec run                 fetch, classify, briefing if due, build
  python -m otasec run --force-briefing
  python -m otasec build               rebuild dist/ from data/ only
  python -m otasec briefing --force    (re)generate today's briefing, then build
  python -m otasec serve en|nl         preview dist/<lang> on http://localhost:8000
"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="otasec")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="full pipeline")
    p_run.add_argument("--force-briefing", action="store_true")
    p_run.add_argument("--no-briefing", action="store_true")
    p_run.add_argument("--no-build", action="store_true")

    sub.add_parser("build", help="render the static site from data/")

    p_brief = sub.add_parser("briefing", help="generate today's briefing")
    p_brief.add_argument("--force", action="store_true")

    p_serve = sub.add_parser("serve", help="local preview")
    p_serve.add_argument("lang", choices=["en", "nl"])
    p_serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    cfg = load_config()

    if args.cmd == "run":
        run(cfg, do_briefing=not args.no_briefing, force_briefing=args.force_briefing,
            build=not args.no_build)
    elif args.cmd == "build":
        run(cfg, fetch=False, classify=False, do_briefing=False)
    elif args.cmd == "briefing":
        run(cfg, fetch=False, classify=False, force_briefing=args.force)
    elif args.cmd == "serve":
        import functools
        import http.server
        root = cfg.dist_dir / args.lang
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        print(f"Serving {root} on http://localhost:{args.port}")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
