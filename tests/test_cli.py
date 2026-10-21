import contextlib
import io
import json
import os
import tempfile
import unittest

from llm_stopcheck import cli


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def write(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        self.addCleanup(os.remove, path)
        return path

    def test_ok_exit_0(self):
        path = self.write({"choices": [{"finish_reason": "stop", "message": {"content": "hi"}}]})
        code, out, _ = run([path])
        self.assertEqual(code, 0)
        self.assertIn("stopcheck=ok", out)

    def test_truncated_exit_1_json(self):
        path = self.write({"choices": [{"finish_reason": "length", "message": {"content": "x"}}]})
        code, out, _ = run([path, "--json", "--max-tokens", "10"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["code"], "truncated")
        self.assertEqual(data["max_tokens"], 10)

    def test_unreadable_exit_2(self):
        self.assertEqual(run(["/nonexistent/file.json"])[0], 2)
        self.assertEqual(run([self.write("not json")])[0], 2)

    def test_usage_exit_2(self):
        self.assertEqual(run([])[0], 2)


class CliExtraTests(CliTests):
    def test_reads_stdin_with_dash(self):
        import unittest.mock as mock
        data = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "hi"}}]})
        with mock.patch("sys.stdin", io.StringIO(data)):
            code, out, _ = run(["-"])
        self.assertEqual((code, "stopcheck=ok" in out), (0, True))

    def test_warnings_go_to_stderr_and_exit_stays_0(self):
        path = self.write({"choices": [{"finish_reason": "stop", "message": {"content": "hi"}}],
                           "usage": {"completion_tokens": 10}})
        code, out, err = run([path, "--max-tokens", "10"])
        self.assertEqual(code, 0)
        self.assertIn("warn=at_limit", out)
        self.assertIn("warnings: at_limit", err)

    def test_help_exits_0(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage:", out)

    def test_module_entry_point(self):
        import subprocess
        import sys
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
        path = self.write({"choices": [{"finish_reason": "length", "message": {"content": "x"}}]})
        r = subprocess.run([sys.executable, "-m", "llm_stopcheck", path], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=src))
        self.assertEqual(r.returncode, 1)
        self.assertIn("stopcheck=truncated", r.stdout)


if __name__ == "__main__":
    unittest.main()
