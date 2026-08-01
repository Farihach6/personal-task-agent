"""Chat API router.

Runs the Reason → Plan agent pipeline and returns the workflow result.
"""

from fastapi import APIRouter, Depends

from app.schemas.agent import AgentRunResponse
from app.schemas.chat import ChatRequest
from app.services.agent_service import AgentService, get_agent_service

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=AgentRunResponse,
)
def chat(
    payload: ChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    """Execute one agent run and return its workflow result."""

    result = service.run(payload.message)

    return AgentRunResponse(**result)