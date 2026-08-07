# routers/chat/chat_router.py
import json

from core.container import Container
from core.exceptions import HTTPError
from core.logger import logger
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse
from schemas.chat.chat_schema import AccountsOut, HoldersOut
from services.chat.portfolio_chat_service import PortfolioChatService

router = APIRouter(prefix="/chat", dependencies=[Depends(verify_access_token)])


def _user_error(exc: Exception) -> str:
    """스트림 중 예외 → 사용자용 한국어 메시지. 도메인 예외(한국어) 외에는 마스킹.

    StreamingResponse 는 응답 시작 후 발생한 예외를 exception_handler 가 못 잡으므로 여기서 매핑한다.
    FastApiMCP 가 올리는 tool 에러('Error calling portfolio_xxx. Status code: 5xx ...' 영문/스택)나
    내부 디테일이 SSE 로 그대로 새지 않게 한다.
    """
    if isinstance(exc, HTTPError):
        return str(exc)  # 도메인 예외는 한국어 메시지 보유 (예: MCP 서버에 연결할 수 없습니다.)
    return "포트폴리오 정보를 가져오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."


@router.get("/accounts")
@inject
async def list_accounts(
    chat_service: PortfolioChatService = Depends(Provide[Container.portfolio_chat_service]),
) -> AccountsOut:
    """좌측 패널/범위 필터용 계좌·포트폴리오 목록 (account_id·name·kind)."""
    accounts = await chat_service.list_accounts()
    return AccountsOut(items=accounts, total_count=len(accounts))


@router.get("/holders")
@inject
async def list_holders(
    chat_service: PortfolioChatService = Depends(Provide[Container.portfolio_chat_service]),
) -> HoldersOut:
    """계좌주 필터 드롭다운용 목록."""
    holders = await chat_service.list_holders()
    return HoldersOut(items=holders, total_count=len(holders))


@router.post("", response_class=StreamingResponse)
@inject
async def chat(
    question: str = Body(..., embed=True),
    account: str | None = Body(None, embed=True),
    since: str | None = Body(None, embed=True),  # YYYY-MM-DD
    until: str | None = Body(None, embed=True),
    kind: str | None = Body(None, embed=True),  # 계좌 유형 (cash | margin | pension …)
    symbols: list[str] | None = Body(None, embed=True),  # 종목 코드·티커 목록
    holders: list[str] | None = Body(None, embed=True),  # 계좌주 email 목록
    history: list[dict] | None = Body(None, embed=True),  # 직전 대화 [{role, content}] (멀티턴, 무상태)
    chat_service: PortfolioChatService = Depends(Provide[Container.portfolio_chat_service]),
):
    """질문 → 포트폴리오 조회 → LLM 답변을 SSE 로 스트리밍. 진행 status·답변 content 이벤트를 JSON 으로 감쌈."""

    async def event_stream():
        try:
            async for event in chat_service.chat(question, account, since, until, kind, symbols, holders, history):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception as e:
            logger.warning(f"chat stream 실패: {e!r}")  # 원본은 서버 로그에만, 클라이언트엔 마스킹 메시지
            yield "data: " + json.dumps({"error": _user_error(e)}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
