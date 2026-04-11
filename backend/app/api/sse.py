"""SSE event bus for processing job fan-out to multiple clients."""

from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    """Per-job event fan-out via asyncio Queues."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Create and register a queue for a job."""
        queue: asyncio.Queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """Remove a queue from a job's subscriber list."""
        if job_id in self._subscribers:
            self._subscribers[job_id] = [q for q in self._subscribers[job_id] if q is not queue]
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    async def publish(self, job_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Send an event to all subscribers for a job."""
        event = {"event": event_type, "data": data}
        for queue in self._subscribers.get(job_id, []):
            await queue.put(event)

    async def close(self, job_id: str) -> None:
        """Send sentinel and cleanup."""
        sentinel = {"event": "close", "data": {}}
        for queue in self._subscribers.get(job_id, []):
            await queue.put(sentinel)
        self._subscribers.pop(job_id, None)
