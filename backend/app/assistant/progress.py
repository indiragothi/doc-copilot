import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import structlog

log = structlog.get_logger()


@contextmanager
def tool_timer(tool: str, **fields: Any) -> Iterator[Callable[..., None]]:
    """Log how long an agent tool took. Call the yielded function to add result fields."""
    started = time.perf_counter()
    result: dict[str, Any] = {}
    yield lambda **extra: result.update(extra)
    log.info(
        "tool_finished",
        tool=tool,
        seconds=round(time.perf_counter() - started, 2),
        **fields,
        **result,
    )
