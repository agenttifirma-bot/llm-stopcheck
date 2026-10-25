"""Command line: check a saved response (file or stdin) and set the exit code.

    llm-stopcheck response.json --max-tokens 3000
    llm-stopcheck a.json b.json --near-limit 0.9 --allow-empty
    curl ... | llm-stopcheck - --json

Several files give one output line each; the exit code is the worst of them.
Exit codes: 0 ok (warnings go to stderr), 1 failed verdict, 2 usage or unreadable input.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, core, errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="llm-stopcheck", description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", metavar="path", help="response JSON file(s), or - for stdin")
    parser.add_argument("--max-tokens", type=int, default=None, help="output cap that was sent")
    parser.add_argument("--near-limit", type=float, default=0.95,
                        help="fraction of --max-tokens that triggers the near_limit warning (default 0.95)")
    parser.add_argument("--allow-empty", action="store_true",
                        help="do not fail on empty content (e.g. tool-call-only responses)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print the verdict as JSON")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return 2 if exit_.code else 0
    if not 0 < args.near_limit <= 1:
        print("llm-stopcheck: --near-limit must be in (0, 1]", file=sys.stderr)
        return 2
    return max(_check_one(path, args) for path in args.paths)


def _check_one(path, args) -> int:
    try:
        if path == "-":
            data = json.load(sys.stdin)
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
    except (OSError, ValueError) as exc:
        print("llm-stopcheck: cannot read input %s: %s" % (path, exc), file=sys.stderr)
        return 2
    verdict = core.check(data, max_tokens=args.max_tokens, near_limit=args.near_limit,
                         require_text=not args.allow_empty)
    if args.as_json:
        print(json.dumps(verdict.as_dict(), sort_keys=True))
    else:
        print(errors.format_record(verdict))
    if verdict.warnings:
        print("warnings: " + ", ".join(verdict.warnings), file=sys.stderr)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
