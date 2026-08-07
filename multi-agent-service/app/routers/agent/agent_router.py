# routers/agent/agent_router.py
import json

from core.auth_context import get_email
from core.container import Container
from core.exceptions import HTTPError
from core.logger import logger
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from schemas.agent.agent_schema import ExampleAIQueryIn, QueryIn
from services.agent.agent_service import AgentService
from services.agent.rate_limit import RateLimiter, StreamSemaphore
from utils.agent.mcp_classify import ALL_MCP_SERVICES


def _switches_to_enabled(b) -> set[str]:
    m = {
        "web": b.switch1,
        "market-data": b.switch2,
        "disclosure": b.switch3,
        "news": b.switch4,
        "doc-search": b.switch5,
        # portfolio 는 프론트 switch 없음 — 항상 활성(보유종목·계좌 조회 tool 바인딩 보장)
        "portfolio": True,
    }
    return {svc for svc, on in m.items() if on}


router = APIRouter(prefix="/agent", dependencies=[Depends(verify_access_token)])


def _user_error(exc: Exception) -> str:
    """스트림 중 예외 → 사용자용 한국어 메시지. 도메인 예외(한국어) 외에는 마스킹.

    StreamingResponse 는 응답 시작 후 발생한 예외를 exception_handler 가 못 잡으므로 여기서 매핑한다.
    """
    if isinstance(exc, HTTPError):
        return str(exc)
    return "멀티 에이전트 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."


@router.post("", response_class=StreamingResponse)
@inject
async def agent_query(
    body: QueryIn,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
    rate_limiter: RateLimiter = Depends(Provide[Container.rate_limiter]),
    stream_semaphore: StreamSemaphore = Depends(Provide[Container.stream_semaphore]),
):
    """질문 → Plan-Execute 멀티 에이전트(5 MCP 서버 도구) → 답변을 SSE 로 스트리밍.

    이벤트(JSON): step(진행)·text(답변)·trace(신뢰도 메타)·error·clarification, 종료 [DONE].
    """
    enabled = set(body.enabled_mcps) if body.enabled_mcps is not None else set(ALL_MCP_SERVICES)
    email = get_email() or "anonymous"
    if not rate_limiter.allow(email):
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 재시도해주세요.")

    async def event_stream():
        async with stream_semaphore.acquire():
            try:
                async for event in agent_service.stream_query(body.question, email, body.gid, enabled):
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            except Exception as e:
                logger.warning(f"agent stream 실패: {e!r}")  # 원본은 서버 로그에만, 클라이언트엔 마스킹
                yield "data: " + json.dumps({"error": _user_error(e)}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/example-ai", response_class=StreamingResponse)
@inject
async def agent_query_example_ai(
    body: ExampleAIQueryIn,
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
    rate_limiter: RateLimiter = Depends(Provide[Container.rate_limiter]),
    stream_semaphore: StreamSemaphore = Depends(Provide[Container.stream_semaphore]),
):
    """ai-chatbot 프론트 호환 SSE 엔드포인트. gid → ai_chat_history 멀티턴 조회 키, switch1-5 → enabled_mcps.

    프레이밍은 newline-delimited JSON(`{json}\\n`, data: prefix 없음). 이벤트 type:
    start·step·routing·tool_parameters·media·response_chunk·title·follow_up_question·workflow_complete·error.
    종료 신호는 workflow_complete (DONE 아님). service 가 항상 마지막에 1회 전송.
    """
    enabled = _switches_to_enabled(body)
    email = get_email() or "anonymous"
    if not rate_limiter.allow(email):
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 재시도해주세요.")

    async def event_stream():
        async with stream_semaphore.acquire():
            try:
                async for event in agent_service.stream_query_example_ai(body.question, email, body.gid, enabled):
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except Exception as e:
                logger.warning(f"example-ai stream 실패: {e!r}")  # 원본은 서버 로그에만, 클라이언트엔 마스킹
                yield json.dumps({"type": "error", "message": _user_error(e)}, ensure_ascii=False) + "\n"
                yield json.dumps({"type": "workflow_complete", "message": "완료되었습니다."}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
