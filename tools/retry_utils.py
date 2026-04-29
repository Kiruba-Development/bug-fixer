import random
import time
from typing import Any, Callable


def is_retryable_error(error: Exception) -> bool:
    message = str(error).lower()
    retry_tokens = [
        "rate limit",
        "rate_limit",
        "too many requests",
        "429",
        "tpm",
        "quota",
        "throttl",
        "timeout",
        "connection",
        "temporarily unavailable",
    ]
    return any(token in message for token in retry_tokens)


def invoke_with_retry(
    func: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    initial_delay: float = 1.5,
    backoff: float = 2.0,
    max_delay: float = 20.0,
    **kwargs: Any,
) -> Any:
    """Invoke a callable with retry/backoff for transient LLM errors."""
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            if attempt == retries or not is_retryable_error(error):
                raise
            time.sleep(delay + random.uniform(0, 0.5))
            delay = min(max_delay, delay * backoff)
    return func(*args, **kwargs)
