"""llm-stopcheck: catch silent LLM failures (truncation, empty output, ...) with a stable error taxonomy."""
from .core import (  # noqa: F401
    ALL_CODES, CONTENT_FILTERED, EMPTY_OUTPUT, HINT_FAIL, HINT_RAISE_MAX_TOKENS, HINT_RETRY,
    MALFORMED_RESPONSE, MISSING_FINISH_REASON, OK, REASONING_EXHAUSTED, REFUSAL, TOOL_CALL_TRUNCATED,
    TRUNCATED, TRUNCATED_EMPTY, UNKNOWN_FINISH_REASON, Verdict, check, extract_text,
)
from .errors import (  # noqa: F401
    ContentFilteredError, EmptyOutputError, ProtocolError, RefusalError, StopcheckError, TruncatedError,
    ensure, format_record, raise_for_verdict,
)

__version__ = "0.1.0"
