import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.thread import Thread
from app.services.agent_service import AgentService


@pytest.mark.asyncio
async def test_thread_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_employee: Employee,
    auth_headers: dict[str, str],
):
    thread_id = uuid.uuid4().hex
    thread = Thread(id=thread_id, employee_id=admin_employee.id)
    db_session.add(thread)
    await db_session.commit()

    response = await client.post(
        "/api/v1/agent/chat",
        headers=auth_headers,
        json={"message": "hello", "thread_id": thread_id},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access to this thread is forbidden."


@pytest.mark.asyncio
async def test_create_new_thread(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
):
    new_thread_id = uuid.uuid4().hex

    try:
        await client.post(
            "/api/v1/agent/chat",
            headers=auth_headers,
            json={"message": "hello", "thread_id": new_thread_id},
        )
    except Exception:
        pass

    # Check if thread is in DB
    thread = await db_session.get(Thread, new_thread_id)
    assert thread is not None


# Mock classes for agent logic testing


async def dummy_events_generator(tools_called=None):
    yield {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("Chunk", (), {"content": "Hello"})},
    }
    if tools_called:
        for tool in tools_called:
            yield {"event": "on_tool_start", "name": tool, "data": {}}
            yield {"event": "on_tool_end", "name": tool, "data": {}}
    yield {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("Chunk", (), {"content": " world"})},
    }


class DummyGraph:
    def __init__(self, tools_called=None):
        self.tools_called = tools_called or []

    async def astream_events(self, input_messages, config, version="v2"):
        async for event in dummy_events_generator(self.tools_called):
            yield event


@pytest.fixture
def mock_graph():
    with patch("app.services.agent_service.get_graph") as mock:
        yield mock


@pytest.fixture
def mock_cache():
    with patch("app.services.agent_service.SemanticCache") as mock:
        yield mock


@pytest.mark.asyncio
async def test_agent_streaming_and_caching(
    db_session: AsyncSession, test_employee: Employee, mock_graph, mock_cache
):
    mock_graph.return_value = DummyGraph(tools_called=[])

    mock_cache_instance = mock_cache.return_value
    mock_cache_instance.get = AsyncMock(return_value=None)
    mock_cache_instance.set = AsyncMock()

    service = AgentService(session=db_session)

    # 1. First request - Cache miss
    events = []
    async for event in service.stream(
        "What is HR?", thread_id="dummy", employee=test_employee
    ):
        events.append(event)

    # Assert streaming tokens were yielded
    assert events[0]["event"] == "token"
    assert json.loads(events[0]["data"])["content"] == "Hello"
    assert events[1]["event"] == "token"
    assert json.loads(events[1]["data"])["content"] == " world"
    assert events[2]["event"] == "done"

    mock_cache_instance.set.assert_called_once_with("What is HR?", "Hello world")

    # 2. Second request - Cache hit
    mock_cache_instance.get = AsyncMock(return_value="Hello world")

    events_cached = []
    async for event in service.stream(
        "What is HR?", thread_id="dummy", employee=test_employee
    ):
        events_cached.append(event)

    assert events_cached[0]["event"] == "cache_hit"
    assert json.loads(events_cached[0]["data"])["content"] == "Hello world"
    assert events_cached[1]["event"] == "done"


@pytest.mark.asyncio
async def test_personal_data_cache_exclusion(
    db_session: AsyncSession, test_employee: Employee, mock_graph, mock_cache
):
    # Simulate agent using a personal data tool
    mock_graph.return_value = DummyGraph(tools_called=["employee_lookup"])

    mock_cache_instance = mock_cache.return_value
    mock_cache_instance.get = AsyncMock(return_value=None)
    mock_cache_instance.set = AsyncMock()

    service = AgentService(session=db_session)

    events = []
    async for event in service.stream(
        "Who am I?", thread_id="dummy", employee=test_employee
    ):
        events.append(event)

    # Assert tool usage was streamed
    assert any(
        e["event"] == "tool_start"
        and json.loads(e["data"])["tool"] == "employee_lookup"
        for e in events
    )
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"])["contains_personal_data"] is True

    mock_cache_instance.set.assert_not_called()
