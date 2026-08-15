"""POST /bot-agent (SSE) · GET /bot-agent/readiness — router=controller(로직 금지)."""

import json

from core.container import Container
from core.logger import logger
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from schemas.bot_agent.bot_agent_schema import BotAgentIn, ReadinessOut
from services.bot_agent.bot_agent_service import BotAgentService

router = APIRouter(prefix="/bot-agent", dependencies=[Depends(verify_access_token)])


@router.get("/readiness", response_model=ReadinessOut)
@inject
async def readiness(
    bot_agent_service: BotAgentService = Depends(Provide[Container.bot_agent_service]),
):
    """대화를 걸 수 있는 상태인가 — 아니면 **이유**를 함께 준다.

    화면이 빈 대화창을 보여주는 대신 「왜 못 쓰는지」를 말할 수 있어야 한다.
    """
    return bot_agent_service.readiness()


@router.post("", response_class=StreamingResponse)
@inject
async def chat(
    body: BotAgentIn,
    bot_agent_service: BotAgentService = Depends(Provide[Container.bot_agent_service]),
):
    """봇 만들기 대화 한 턴을 SSE 로 스트리밍 (text·tool·result·unavailable·error + [DONE])."""

    async def event_stream():
        try:
            async for event in bot_agent_service.stream(body.message):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception as e:
            # StreamingResponse 는 응답 시작 후 예외를 exception_handler 가 못 잡는다 —
            # 여기서 마스킹하고 원본은 로그에만 남긴다.
            logger.warning(f"bot-agent stream 실패: {e!r}")
            error = {"type": "error", "message": "대화 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."}
            yield "data: " + json.dumps(error, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
