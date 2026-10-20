import unittest

import llm_stopcheck as sc


def resp(content="hello", finish="stop", native=None, usage=None, **message):
    msg = {"role": "assistant", "content": content}
    msg.update(message)
    choice = {"index": 0, "finish_reason": finish, "message": msg}
    if native is not None:
        choice["native_finish_reason"] = native
    out = {"choices": [choice]}
    if usage is not None:
        out["usage"] = usage
    return out


class CheckTests(unittest.TestCase):
    def test_ok(self):
        v = sc.check(resp())
        self.assertTrue(v.ok)
        self.assertEqual(v.code, sc.OK)
        self.assertIsNone(v.hint)

    def test_truncated_with_text(self):
        v = sc.check(resp("half an ans", finish="length"))
        self.assertFalse(v.ok)
        self.assertEqual(v.code, sc.TRUNCATED)
        self.assertEqual(v.hint, sc.HINT_RAISE_MAX_TOKENS)

    def test_todays_case_reasoning_exhausted(self):
        r = resp("", finish="length", reasoning_content="thinking...",
                 usage={"completion_tokens": 3000, "completion_tokens_details": {"reasoning_tokens": 3000}})
        v = sc.check(r, max_tokens=3000)
        self.assertEqual(v.code, sc.REASONING_EXHAUSTED)
        self.assertEqual(v.reasoning_tokens, 3000)
        self.assertEqual(v.hint, sc.HINT_RAISE_MAX_TOKENS)

    def test_truncated_empty_without_reasoning(self):
        self.assertEqual(sc.check(resp("", finish="length")).code, sc.TRUNCATED_EMPTY)

    def test_tool_call_truncated(self):
        v = sc.check(resp(None, finish="length", tool_calls=[{"id": "1"}]))
        self.assertEqual(v.code, sc.TOOL_CALL_TRUNCATED)

    def test_native_finish_reason_reveals_truncation(self):
        v = sc.check(resp("cut", finish="stop", native="MAX_TOKENS"))
        self.assertEqual(v.code, sc.TRUNCATED)
        self.assertIn("native_finish_reason", v.reason)

    def test_anthropic_style(self):
        v = sc.check(resp("cut", finish="max_tokens"))
        self.assertEqual(v.code, sc.TRUNCATED)

    def test_content_filter(self):
        v = sc.check(resp("", finish="content_filter"))
        self.assertEqual(v.code, sc.CONTENT_FILTERED)
        self.assertEqual(v.hint, sc.HINT_FAIL)

    def test_refusal_field(self):
        v = sc.check(resp(None, refusal="I can't help with that"))
        self.assertEqual(v.code, sc.REFUSAL)

    def test_empty_output(self):
        v = sc.check(resp("  "))
        self.assertEqual(v.code, sc.EMPTY_OUTPUT)
        self.assertTrue(sc.check(resp(""), require_text=False).ok)

    def test_tool_calls_need_no_text(self):
        self.assertTrue(sc.check(resp(None, finish="tool_calls", tool_calls=[{"id": "1"}])).ok)

    def test_missing_finish(self):
        r = resp()
        r["choices"][0]["finish_reason"] = None
        self.assertEqual(sc.check(r).code, sc.MISSING_FINISH_REASON)

    def test_unknown_finish(self):
        self.assertEqual(sc.check(resp(finish="weird")).code, sc.UNKNOWN_FINISH_REASON)

    def test_malformed(self):
        for bad in (None, "x", {}, {"choices": []}, {"choices": ["x"]}):
            self.assertEqual(sc.check(bad).code, sc.MALFORMED_RESPONSE)

    def test_content_parts(self):
        r = resp([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
        self.assertTrue(sc.check(r).ok)
        self.assertEqual(sc.extract_text(r), "ab")

    def test_model_dump_objects(self):
        class Obj:
            def model_dump(self):
                return resp()
        self.assertTrue(sc.check(Obj()).ok)

    def test_limit_warnings(self):
        near = sc.check(resp(usage={"completion_tokens": 96}), max_tokens=100)
        self.assertTrue(near.ok)
        self.assertEqual(near.warnings, ["near_limit"])
        at = sc.check(resp(usage={"completion_tokens": 100}), max_tokens=100)
        self.assertEqual(at.warnings, ["at_limit"])
        self.assertEqual(sc.check(resp(usage={"completion_tokens": 10}), max_tokens=100).warnings, [])

    def test_all_codes_reachable_names(self):
        self.assertEqual(len(set(sc.ALL_CODES)), len(sc.ALL_CODES))


class ErrorTests(unittest.TestCase):
    def test_ensure_returns_text(self):
        self.assertEqual(sc.ensure(resp("hi")), "hi")

    def test_ensure_raises_typed(self):
        with self.assertRaises(sc.TruncatedError) as cm:
            sc.ensure(resp("x", finish="length"))
        self.assertEqual(cm.exception.code, sc.TRUNCATED)
        self.assertEqual(cm.exception.hint, sc.HINT_RAISE_MAX_TOKENS)
        with self.assertRaises(sc.EmptyOutputError):
            sc.ensure(resp(""))
        with self.assertRaises(sc.ContentFilteredError):
            sc.ensure(resp("", finish="content_filter"))
        with self.assertRaises(sc.RefusalError):
            sc.ensure(resp(None, refusal="no"))
        with self.assertRaises(sc.ProtocolError):
            sc.ensure({})

    def test_format_record_ascii_and_sanitised(self):
        v = sc.check(resp("x", finish="length"), max_tokens=3000)
        line = sc.format_record(v, model="evil model\nstopcheck=ok", run=None)
        self.assertNotIn("\n", line)
        self.assertTrue(line.isascii())
        self.assertIn("stopcheck=truncated", line)
        self.assertIn("run=-", line)
        self.assertEqual(line.count("stopcheck="), 1)  # injected "=" is neutralised, no fake key
        self.assertIn("model=evil_model_stopcheck_ok", line)


if __name__ == "__main__":
    unittest.main()
