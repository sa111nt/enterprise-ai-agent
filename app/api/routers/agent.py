from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import RateLimiter, get_agent_service, get_current_employee
from app.models.employee import Employee
from app.schemas.agent import ChatRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post(
    "/chat",
    dependencies=[Depends(RateLimiter(requests=10, window_seconds=60))],
    summary="Chat with the AI HR assistant (SSE streaming)",
    response_description="Server-Sent Events stream with agent response tokens",
)
async def chat(
    body: ChatRequest,
    employee: Employee = Depends(get_current_employee),
    service: AgentService = Depends(get_agent_service),
):
    thread_id = await service.validate_thread(body.thread_id, employee.id)
    return EventSourceResponse(
        service.stream(body.message, thread_id, employee),
        media_type="text/event-stream",
    )
