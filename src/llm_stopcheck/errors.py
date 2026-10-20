"""Exceptions for callers who prefer raising over inspecting a verdict."""
from __future__ import annotations

import re
from typing import Any

from . import core


class StopcheckError(Exception):
    """Base class. ``.verdict`` holds the full ``Verdict``; ``.code`` its code."""

    def __init__(self, verdict: core.Verdict):
        super().__init__("%s: %s" % (verdict.code, verdict.reason))
        self.verdict = verdict

    @property
    def code(self) -> str:
        return self.verdict.code

    @property
    def hint(self):
        return self.verdict.hint


class TruncatedError(StopcheckError):
    """Output cap reached (truncated, truncated_empty, reasoning_exhausted, tool_call_truncated)."""


class EmptyOutputError(StopcheckError):
    """Finished normally but produced no content."""


class ContentFilteredError(StopcheckError):
    """Blocked by a provider content filter."""


class RefusalError(StopcheckError):
    """The model refused."""


class ProtocolError(StopcheckError):
    """Malformed response, missing or unknown finish reason."""


_ERROR_FOR_CODE = {
    core.TRUNCATED: TruncatedError,
    core.TRUNCATED_EMPTY: TruncatedError,
    core.REASONING_EXHAUSTED: TruncatedError,
    core.TOOL_CALL_TRUNCATED: TruncatedError,
    core.EMPTY_OUTPUT: EmptyOutputError,
    core.CONTENT_FILTERED: ContentFilteredError,
    core.REFUSAL: RefusalError,
    core.MISSING_FINISH_REASON: ProtocolError,
    core.UNKNOWN_FINISH_REASON: ProtocolError,
    core.MALFORMED_RESPONSE: ProtocolError,
}


def raise_for_verdict(verdict: core.Verdict) -> core.Verdict:
    """Raise the matching ``StopcheckError`` subclass unless the verdict is ok."""
    if verdict.ok:
        return verdict
    raise _ERROR_FOR_CODE.get(verdict.code, StopcheckError)(verdict)


def ensure(response: Any, **kwargs) -> str:
    """Return the response text, or raise a ``StopcheckError``. kwargs go to ``check``."""
    raise_for_verdict(core.check(response, **kwargs))
    return core.extract_text(response)


_SAFE = re.compile(r"[^A-Za-z0-9_.:/+-]")


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return _SAFE.sub("_", str(value))[:60]


def format_record(verdict: core.Verdict, **extra: Any) -> str:
    """One ASCII ``key=value`` line for logs. Values are sanitised, so log injection is impossible.

    Example: ``stopcheck=truncated finish=length tokens=12510/3000 reasoning_tokens=- hint=raise_max_tokens``
    """
    tokens = "%s/%s" % (_value(verdict.completion_tokens), _value(verdict.max_tokens))
    parts = [
        "stopcheck=" + _value(verdict.code),
        "finish=" + _value(verdict.finish_reason),
        "native=" + _value(verdict.native_finish_reason),
        "tokens=" + tokens,
        "reasoning_tokens=" + _value(verdict.reasoning_tokens),
        "hint=" + _value(verdict.hint),
    ]
    if verdict.warnings:
        parts.append("warn=" + _value(",".join(verdict.warnings)))
    for key, value in extra.items():
        parts.append("%s=%s" % (_SAFE.sub("_", str(key))[:30], _value(value)))
    return " ".join(parts)
