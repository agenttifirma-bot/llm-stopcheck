# Changelog

## 0.1.0

- `check()` classifies chat-completion responses: truncated, truncated_empty, reasoning_exhausted,
  tool_call_truncated, empty_output, content_filtered, refusal, missing/unknown finish reason, malformed.
- `ensure()` and typed exceptions; `format_record()` for safe one-line log records.
- `llm-stopcheck` CLI (exit 0 ok, 1 failed verdict, 2 usage).
- Standard library only, Python 3.10+.
