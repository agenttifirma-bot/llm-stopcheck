import os
import re
import unittest

import llm_stopcheck as sc
from llm_stopcheck import core

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")

EXPECTED_HINTS = {
    core.OK: "-",
    core.TRUNCATED: core.HINT_RAISE_MAX_TOKENS,
    core.TRUNCATED_EMPTY: core.HINT_RAISE_MAX_TOKENS,
    core.REASONING_EXHAUSTED: core.HINT_RAISE_MAX_TOKENS,
    core.TOOL_CALL_TRUNCATED: core.HINT_RAISE_MAX_TOKENS,
    core.EMPTY_OUTPUT: core.HINT_RETRY,
    core.CONTENT_FILTERED: core.HINT_FAIL,
    core.REFUSAL: core.HINT_FAIL,
    core.MISSING_FINISH_REASON: core.HINT_RETRY,
    core.UNKNOWN_FINISH_REASON: core.HINT_RETRY,
    core.MALFORMED_RESPONSE: core.HINT_RETRY,
}

ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|.*\|\s*(`([^`]+)`|-)\s*\|\s*$")


def readme_tables():
    """Code/hint tables of the README (English first, then Finnish) as lists of (code, hint)."""
    tables, current = [], None
    with open(README, encoding="utf-8") as fh:
        for line in fh:
            if re.match(r"^\|\s*code\s*\|", line):
                current = []
                tables.append(current)
            elif current is not None:
                m = ROW.match(line.rstrip("\n"))
                if m:
                    current.append((m.group(1), m.group(3) or "-"))
                elif not line.startswith("|"):
                    current = None
    return tables


class ReadmeSyncTests(unittest.TestCase):
    def test_two_tables_found(self):
        self.assertEqual(len(readme_tables()), 2)

    def test_expected_hints_cover_all_codes(self):
        self.assertEqual(set(EXPECTED_HINTS), set(sc.ALL_CODES))

    def test_codes_match_all_codes_in_order(self):
        for i, table in enumerate(readme_tables()):
            with self.subTest(table="en" if i == 0 else "fi"):
                self.assertEqual([code for code, _ in table], list(sc.ALL_CODES))

    def test_hints_match_core(self):
        for i, table in enumerate(readme_tables()):
            with self.subTest(table="en" if i == 0 else "fi"):
                self.assertEqual(dict(table), EXPECTED_HINTS)


if __name__ == "__main__":
    unittest.main()
