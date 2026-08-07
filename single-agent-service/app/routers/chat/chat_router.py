# ── [가이드 9/9] routers/chat/chat_router.py — POST /chat (SSE). router=controller(로직 금지) ──
# 무엇: 질문을 받아 service.stream_chat 의 이벤트를 SSE 로 흘린다. 프레이밍 data: {json}\n\n, 종료 [DONE].
# 복사 후: prefix·body 모델. SSE 프레이밍/예외 마스킹 골격은 그대로.
# 함정: dependencies=[Depends(verify_access_token)] 인증 필수 · StreamingResponse 는 응답 시작 후 예외를
#   exception_handler 가 못 잡으므로 여기서 {"type":"error"} 로 마스킹(원본은 로그만) · @inject + Provide ·
#   ensure_ascii=False(한글) · media_type="text/event-stream".

import json

from core.container import Container
from core.logger import logger
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from schemas.chat.chat_schema import ChatIn
from services.chat.chat_service import ChatService

router = APIRouter(prefix="/chat", dependencies=[Depends(verify_access_token)])


@router.post("", response_class=StreamingResponse)
@inject
async def chat(
    body: ChatIn,
    chat_service: ChatService = Depends(Provide[Container.chat_service]),
):
    """질문 → 웹 검색 tool 호출 → LLM 답변을 SSE 로 스트리밍 (step·token·error + [DONE])."""

    async def event_stream():
        try:
            async for event in chat_service.stream_chat(body.question):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception as e:
            logger.warning(f"chat stream 실패: {e!r}")  # 원본은 서버 로그에만, 클라이언트엔 마스킹
            error = {"type": "error", "message": "답변 생성 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."}
            yield "data: " + json.dumps(error, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
