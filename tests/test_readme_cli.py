"""Locks the README CLI example line and the exit code 2 cases to the real CLI."""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest

from llm_stopcheck import cli

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")

# Input that produces the README example (reasoning model used the whole 3000-token budget).
EXAMPLE_RESPONSE = {
    "choices": [{"finish_reason": "length", "message": {"content": ""}}],
    "usage": {"completion_tokens": 3000, "completion_tokens_details": {"reasoning_tokens": 3000}},
}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def readme_example_line():
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"Output \(one line per file\):\s*`(stopcheck=[^`]+)`", text)
    assert m, "README output example not found"
    return m.group(1)


class ReadmeCliTests(unittest.TestCase):
    def write(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(os.remove, path)
        return path

    def test_example_line_matches_readme(self):
        code, out, _ = run([self.write(EXAMPLE_RESPONSE), "--max-tokens", "3000"])
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), readme_example_line())

    def test_exit_2_for_invalid_flags(self):
        path = self.write(EXAMPLE_RESPONSE)
        for flags in (["--max-tokens", "0"], ["--max-tokens", "-5"],
                      ["--near-limit", "0"], ["--near-limit", "1.5"], ["--near-limit", "-0.1"]):
            with self.subTest(flags=flags):
                code, out, err = run([path] + flags)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("llm-stopcheck:", err)

    def test_near_limit_one_is_valid(self):
        code, _, _ = run([self.write(EXAMPLE_RESPONSE), "--near-limit", "1"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
