import asyncio
from collections.abc import AsyncIterator

STUB_REPLY = (
    "This is a stubbed response. Document search and cited answers "
    "will replace it once retrieval is connected."
)
CHUNK_DELAY_SECONDS = 0.05


async def stub_reply() -> AsyncIterator[str]:
    """Placeholder for the real turn (retrieve → agent → validate)."""
    for word in STUB_REPLY.split(" "):
        yield word + " "
        await asyncio.sleep(CHUNK_DELAY_SECONDS)
