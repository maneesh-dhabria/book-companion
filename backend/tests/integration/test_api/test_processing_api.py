"""Integration tests for processing API and SSE event bus."""

import asyncio

import pytest

from app.api.sse import EventBus


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    queue = bus.subscribe("job-1")
    await bus.publish("job-1", "section_started", {"section_id": 5})
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["event"] == "section_started"
    assert event["data"]["section_id"] == 5
    bus.unsubscribe("job-1", queue)


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers():
    bus = EventBus()
    q1 = bus.subscribe("job-1")
    q2 = bus.subscribe("job-1")
    await bus.publish("job-1", "section_completed", {"section_id": 5})
    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1 == e2
    bus.unsubscribe("job-1", q1)
    bus.unsubscribe("job-1", q2)


@pytest.mark.asyncio
async def test_event_bus_close():
    bus = EventBus()
    queue = bus.subscribe("job-2")
    await bus.close("job-2")
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["event"] == "close"


@pytest.mark.asyncio
async def test_processing_status_not_found(client):
    resp = await client.get("/api/v1/processing/99999/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_nonexistent_job(client):
    resp = await client.post("/api/v1/processing/99999/cancel")
    assert resp.status_code == 404
