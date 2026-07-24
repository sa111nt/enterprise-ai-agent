import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_graph
from app.agent.tools import PERSONAL_DATA_TOOLS
from app.core.redis import get_redis_client
from app.models.employee import Employee
from app.models.thread import Thread
from app.rag.cache import SemanticCache

logger = logging.getLogger(__name__)

PERSONAL_QUERY_PATTERN = re.compile(
    r"\b(my|me|mine|i)\b",
    re.IGNORECASE,
)


def is_personal_query(message: str) -> bool:
    return bool(PERSONAL_QUERY_PATTERN.search(message))


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cache = SemanticCache(get_redis_client())

    async def validate_thread(self, thread_id: str | None, employee_id: int) -> str:
        if thread_id is None:
            new_thread_id = uuid.uuid4().hex
            thread = Thread(id=new_thread_id, employee_id=employee_id)
            self.session.add(thread)
            await self.session.commit()
            return new_thread_id

        existing_thread = await self.session.get(Thread, thread_id)
        if existing_thread is None:
            thread = Thread(id=thread_id, employee_id=employee_id)
            self.session.add(thread)
            await self.session.commit()
        elif existing_thread.employee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this thread is forbidden.",
            )
        return thread_id

    async def stream(
        self,
        message: str,
        thread_id: str,
        employee: Employee,
    ) -> AsyncGenerator[dict, None]:
        # 1. Check semantic cache (only for non-personal queries)
        is_personal = is_personal_query(message)
        if not is_personal:
            cached_answer = await self.cache.get(message)
            if cached_answer is not None:
                yield {
                    "event": "cache_hit",
                    "data": json.dumps({"content": cached_answer}),
                }
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "thread_id": thread_id,
                            "contains_personal_data": False,
                        }
                    ),
                }
                return

        # 2. Build input with employee context
        enriched = (
            f"[Current user: {employee.first_name} {employee.last_name}, "
            f"employee_id={employee.id}]\n\n{message}"
        )
        input_messages = {"messages": [HumanMessage(content=enriched)]}
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "employee_id": employee.id,
                "employee_role": employee.role.value,
            }
        }

        # 3. Stream agent response
        graph = get_graph()
        full_response = ""
        tools_called: set[str] = set()

        async for event in graph.astream_events(input_messages, config, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    full_response += chunk.content
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": chunk.content}),
                    }

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tools_called.add(tool_name)
                yield {
                    "event": "tool_start",
                    "data": json.dumps({"tool": tool_name}),
                }

            elif kind == "on_tool_end":
                yield {
                    "event": "tool_end",
                    "data": json.dumps({"tool": event.get("name", "")}),
                }

        # 4. Determine privacy flag
        has_personal_tool = bool(tools_called & PERSONAL_DATA_TOOLS)
        contains_personal_data = is_personal or has_personal_tool

        # 5. Cache if strictly no personal data and contains response
        if not contains_personal_data and full_response:
            await self.cache.set(message, full_response)

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "thread_id": thread_id,
                    "contains_personal_data": contains_personal_data,
                }
            ),
        }
