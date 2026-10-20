"""Command line: check a saved response (file or stdin) and set the exit code.

    llm-stopcheck response.json --max-tokens 3000
    curl ... | llm-stopcheck - --json

Exit codes: 0 ok (warnings go to stderr), 1 failed verdict, 2 usage or unreadable input.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import core, errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="llm-stopcheck", description=__doc__.split("\n\n")[0])
    parser.add_argument("path", help="response JSON file, or - for stdin")
    parser.add_argument("--max-tokens", type=int, default=None, help="output cap that was sent")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print the verdict as JSON")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return 2 if exit_.code else 0
    try:
        if args.path == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.path, encoding="utf-8") as f:
                data = json.load(f)
    except (OSError, ValueError) as exc:
        print("llm-stopcheck: cannot read input: %s" % exc, file=sys.stderr)
        return 2
    verdict = core.check(data, max_tokens=args.max_tokens)
    if args.as_json:
        print(json.dumps(verdict.as_dict(), sort_keys=True))
    else:
        print(errors.format_record(verdict))
    if verdict.warnings:
        print("warnings: " + ", ".join(verdict.warnings), file=sys.stderr)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
