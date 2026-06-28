from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_agent_service, get_current_employee
from app.models.employee import Employee
from app.schemas.agent import ChatRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post(
    "/chat",
    summary="Chat with the AI HR assistant (SSE streaming)",
    response_description="Server-Sent Events stream with agent response tokens",
)
async def chat(
    body: ChatRequest,
    service: AgentService = Depends(get_agent_service),
    current_employee: Employee = Depends(get_current_employee),
) -> EventSourceResponse:
    return EventSourceResponse(
        service.stream(
            message=body.message,
            thread_id=body.thread_id,
            employee=current_employee,
        )
    )
