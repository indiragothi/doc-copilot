import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
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


@dataclass
class ProgressReporter:
    """Reports what the agent is doing so the analyst sees live status while waiting.

    Each step is reported when it starts and again when it ends, under the same `id`.
    The default sink drops events, which is what tests and CLIs want.
    """

    sink: Callable[[dict[str, Any]], None] = lambda event: None
    _count: int = field(default=0, init=False)

    @contextmanager
    def step(
        self, label: str, detail: str | None = None
    ) -> Iterator[Callable[[str], None]]:
        """Wrap one unit of work. The yielded function sets the detail shown when it ends."""
        self._count += 1
        event = {"id": f"step-{self._count}", "label": label}
        self.sink({**event, "detail": detail, "state": "running"})
        outcome = {"detail": detail}
        try:
            yield lambda text: outcome.update(detail=text)
        except BaseException:
            self.sink({**event, **outcome, "state": "failed"})
            raise
        self.sink({**event, **outcome, "state": "done"})
