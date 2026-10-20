"""Classify LLM chat-completion responses and catch silent failures.

A response with HTTP 200 can still be unusable: cut off at the token cap, empty because a reasoning
model spent its whole budget thinking, filtered, or missing a finish reason. ``check`` turns the
response into a small, stable verdict (a code, a reason and a retry hint) so that pipelines can
fail loudly instead of passing half an answer downstream.

Standard library only. Works on parsed OpenAI-compatible JSON (OpenAI, LiteLLM, OpenRouter, vLLM,
Ollama, DeepSeek, ...). Objects with ``model_dump()`` / ``to_dict()`` are accepted too.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Finish reasons (OpenAI-style and provider-native spellings, lower-cased, "-" -> "_").
TRUNCATED_REASONS = frozenset({
    "length", "max_tokens", "max_output_tokens", "model_length", "max_tokens_exceeded",
    "model_context_window_exceeded", "context_length_exceeded",
})
FILTERED_REASONS = frozenset({
    "content_filter", "safety", "recitation", "blocklist", "prohibited_content", "spii", "image_safety",
})
REFUSAL_REASONS = frozenset({"refusal"})
OK_REASONS = frozenset({
    "stop", "end_turn", "stop_sequence", "tool_calls", "tool_use", "function_call",
})

# Result codes (the stable taxonomy).
OK = "ok"
TRUNCATED = "truncated"
TRUNCATED_EMPTY = "truncated_empty"
REASONING_EXHAUSTED = "reasoning_exhausted"
TOOL_CALL_TRUNCATED = "tool_call_truncated"
EMPTY_OUTPUT = "empty_output"
CONTENT_FILTERED = "content_filtered"
REFUSAL = "refusal"
MISSING_FINISH_REASON = "missing_finish_reason"
UNKNOWN_FINISH_REASON = "unknown_finish_reason"
MALFORMED_RESPONSE = "malformed_response"

ALL_CODES = (
    OK, TRUNCATED, TRUNCATED_EMPTY, REASONING_EXHAUSTED, TOOL_CALL_TRUNCATED, EMPTY_OUTPUT,
    CONTENT_FILTERED, REFUSAL, MISSING_FINISH_REASON, UNKNOWN_FINISH_REASON, MALFORMED_RESPONSE,
)

# Retry hints.
HINT_RAISE_MAX_TOKENS = "raise_max_tokens"
HINT_RETRY = "retry"
HINT_FAIL = "fail"


@dataclass
class Verdict:
    """Outcome of ``check``. ``ok`` is False for every code except ``ok``."""

    ok: bool
    code: str
    reason: str
    finish_reason: Optional[str] = None
    native_finish_reason: Optional[str] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    content_chars: int = 0
    hint: Optional[str] = None
    warnings: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _as_dict(response: Any) -> Optional[dict]:
    if isinstance(response, dict):
        return response
    for name in ("model_dump", "to_dict", "dict"):
        fn = getattr(response, name, None)
        if callable(fn):
            try:
                data = fn()
            except Exception:  # noqa: BLE001 - any failure just means "not convertible"
                continue
            if isinstance(data, dict):
                return data
    return None


def _norm(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_")
    return text or None


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    return None


def _text_of(content: Any) -> str:
    """Plain text of a message ``content`` that is a string or a list of text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def extract_text(response: Any) -> str:
    """Text of the first choice, or an empty string."""
    data = _as_dict(response)
    try:
        message = data["choices"][0].get("message") or {}
    except (TypeError, KeyError, IndexError, AttributeError):
        return ""
    return _text_of(message.get("content"))


def check(response: Any, *, max_tokens: Optional[int] = None, near_limit: float = 0.95,
          require_text: bool = True) -> Verdict:
    """Classify a chat-completion response. Never raises; bad input gives ``malformed_response``.

    ``max_tokens`` is the output cap you sent. With it, ``near_limit`` / ``at_limit`` warnings are
    added to otherwise fine responses. ``require_text=False`` allows empty content (e.g. when you
    only care about tool calls)."""
    data = _as_dict(response)
    if data is None:
        return Verdict(False, MALFORMED_RESPONSE, "response is not a mapping", max_tokens=max_tokens,
                       hint=HINT_RETRY)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return Verdict(False, MALFORMED_RESPONSE, "response has no choices", max_tokens=max_tokens,
                       hint=HINT_RETRY)
    choice = choices[0]
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}

    finish = _norm(choice.get("finish_reason"))
    native = _norm(choice.get("native_finish_reason"))
    if native is None and isinstance(choice.get("provider_specific_fields"), dict):
        native = _norm(choice["provider_specific_fields"].get("native_finish_reason"))

    text = _text_of(message.get("content"))
    tool_calls = message.get("tool_calls") or message.get("function_call")
    reasoning_text = _text_of(message.get("reasoning_content")) or _text_of(message.get("reasoning"))

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    completion = _int(usage.get("completion_tokens"))
    if completion is None:
        completion = _int(usage.get("output_tokens"))
    details = usage.get("completion_tokens_details")
    reasoning_tokens = _int(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    if reasoning_tokens is None:
        reasoning_tokens = _int(usage.get("reasoning_tokens"))

    def verdict(ok: bool, code: str, reason: str, hint: Optional[str] = None, warnings=None) -> Verdict:
        return Verdict(ok, code, reason, finish_reason=finish, native_finish_reason=native,
                       completion_tokens=completion, reasoning_tokens=reasoning_tokens,
                       max_tokens=max_tokens, content_chars=len(text), hint=hint,
                       warnings=list(warnings or []))

    if finish is None:
        return verdict(False, MISSING_FINISH_REASON,
                       "no finish_reason: the response may have been cut off or the stream ended early",
                       HINT_RETRY)

    if finish in TRUNCATED_REASONS or native in TRUNCATED_REASONS:
        mismatch = "" if finish in TRUNCATED_REASONS else (
            " (finish_reason says %r but native_finish_reason says %r)" % (finish, native))
        if tool_calls:
            return verdict(False, TOOL_CALL_TRUNCATED,
                           "output cap reached while writing a tool call; arguments are incomplete"
                           + mismatch, HINT_RAISE_MAX_TOKENS)
        if not text.strip():
            if reasoning_tokens or reasoning_text.strip():
                return verdict(False, REASONING_EXHAUSTED,
                               "output cap reached before any answer: the model spent its budget on "
                               "reasoning" + mismatch, HINT_RAISE_MAX_TOKENS)
            return verdict(False, TRUNCATED_EMPTY, "output cap reached with empty content" + mismatch,
                           HINT_RAISE_MAX_TOKENS)
        return verdict(False, TRUNCATED, "output cap reached; the answer is cut off" + mismatch,
                       HINT_RAISE_MAX_TOKENS)

    if finish in FILTERED_REASONS or native in FILTERED_REASONS:
        return verdict(False, CONTENT_FILTERED, "response blocked by a content filter", HINT_FAIL)

    refusal_text = message.get("refusal")
    if finish in REFUSAL_REASONS or (isinstance(refusal_text, str) and refusal_text.strip()):
        return verdict(False, REFUSAL, "the model refused to answer", HINT_FAIL)

    if finish not in OK_REASONS:
        return verdict(False, UNKNOWN_FINISH_REASON, "unrecognised finish_reason %r" % finish, HINT_RETRY)

    if require_text and not tool_calls and not text.strip():
        return verdict(False, EMPTY_OUTPUT, "finish_reason %r but the content is empty" % finish, HINT_RETRY)

    warnings = []
    if max_tokens and completion is not None:
        if completion >= max_tokens:
            warnings.append("at_limit")
        elif completion >= near_limit * max_tokens:
            warnings.append("near_limit")
    return verdict(True, OK, "ok", None, warnings)
