# services/chat/portfolio_chat_service.py
from collections.abc import AsyncGenerator

from clients.mcp.mcp_agent import stream_mcp_agent
from clients.mcp.mcp_client import call_mcp_tool, get_cached_instructions
from clients.mcp.mcp_prompt import compose_system_prompt
from core.exceptions import ServiceUnavailableError
from core.logger import logger
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from schemas.chat.chat_schema import ChatAccountInfo, ChatHolderInfo
from utils.chat.chat_utils import date_context, lc_history, scope_note
from utils.common.time_utils import now_kst

# portfolio-mcp `AccountInfo` 에서 계좌주 신원을 담을 필드명. 지금 생산자에는 둘 다 없다 (#368) —
# 이름을 여기 한 곳에 두어 생산자가 필드를 추가하면 계약 검증 스크립트가 이 상수와 대조한다.
HOLDER_NAME_FIELD = "holder"
HOLDER_EMAIL_FIELD = "holder_email"


class PortfolioChatService:
    """포트폴리오 활동 기반 챗. 데이터는 portfolio-mcp-service MCP tool 을 LLM 이 직접 호출(LangGraph 에이전트).

    list_accounts/list_holders(좌측 패널·드롭다운)도 MCP tool 호출로 처리.
    chat()은 멀티 MCP(MultiServerMCPClient) tool-calling 에이전트 + 답변 스트리밍.
    """

    def __init__(self, mcp_client: MultiServerMCPClient, chat_client: ChatOpenAI):
        self.mcp_client = mcp_client
        self.chat_client = chat_client

    async def list_accounts(self) -> list[ChatAccountInfo]:
        """좌측 패널/범위 필터용 — MCP portfolio_list_accounts 응답을 뷰 모델로 매핑.

        계약의 정본은 생산자(portfolio-mcp `AccountInfo`)이고 필드명이 다르다 —
        account_name→name · account_type→kind · base_currency→base_ccy (#368).
        """
        items = await self._fetch_accounts()
        accounts: list[ChatAccountInfo] = []
        skipped = 0
        for acc in items:
            account_id = acc.get("account_id") or ""
            if not account_id:
                skipped += 1
                continue
            accounts.append(
                ChatAccountInfo(
                    account_id=account_id,
                    name=acc.get("account_name") or "",
                    kind=acc.get("account_type") or "",
                    base_ccy=acc.get("base_currency") or "",
                )
            )
        if skipped:
            logger.warning("[chat] 계좌 목록 — account_id 없는 항목 %d/%d 건 제외", skipped, len(items))
        return accounts

    async def list_holders(self) -> list[ChatHolderInfo]:
        """계좌주 필터 드롭다운용 — MCP portfolio_list_accounts 응답에서 계좌주 신원을 추출.

        ⚠️ 생산자 계약(portfolio-mcp `AccountInfo`)에 계좌주 신원 필드가 **없어 이 목록은 늘 비어
        있다**(#368). 종전 코드는 신원이 없으면 계좌 별칭을 사람 이름 자리에 끼워 넣는 폴백을
        두었는데, 없는 데이터를 지어내는 쪽이라 걷어내고 빈 결과를 로그로 드러낸다.
        """
        items = await self._fetch_accounts()
        seen: dict[str, ChatHolderInfo] = {}
        for acc in items:
            name = acc.get(HOLDER_NAME_FIELD) or ""
            email = acc.get(HOLDER_EMAIL_FIELD) or ""
            key = email or name
            if key and key not in seen:
                seen[key] = ChatHolderInfo(account_id=acc.get("account_id") or "", name=name, email=email)
        if items and not seen:
            logger.warning(
                "[chat] 계좌주 목록이 비었다 — portfolio-mcp 응답 %d건에 계좌주 필드(%s/%s)가 없다 (#368)",
                len(items),
                HOLDER_NAME_FIELD,
                HOLDER_EMAIL_FIELD,
            )
        return list(seen.values())

    async def _fetch_accounts(self) -> list[dict]:
        """MCP 계좌 목록 원본. 외부 서비스 응답이므로 여기서 형태를 검증한다(경계 검증)."""
        data = await call_mcp_tool(self.mcp_client, "portfolio_list_accounts")
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ServiceUnavailableError("포트폴리오 계좌 목록을 가져오지 못했습니다.")
        return [acc for acc in items if isinstance(acc, dict)]

    async def chat(
        self,
        question: str,
        account: str | None,
        since: str | None = None,
        until: str | None = None,
        kind: str | None = None,
        symbols: list[str] | None = None,
        holders: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """질문 → LLM 이 등록된 MCP tool 을 호출(에이전트) → 답변 스트리밍.

        진행 단계는 ``{"status": ...}``, 답변 토큰은 ``{"content": ...}`` 이벤트로 yield.
        UI 조건(account/kind/symbols/holders/since/until)은 system 프롬프트 범위로 주입 — LLM 이 도구 인자에 반영.
        history 는 멀티턴(매 요청 동봉, 서버 무상태).
        """
        scope = scope_note(account, since, until, kind, symbols, holders)
        dynamic = f"## 오늘 날짜와 기간 기준 (KST)\n{date_context(now_kst())}" + (
            f"\n\n## 기본 조회 범위\n{scope}" if scope else ""
        )
        domain_blocks = await get_cached_instructions(self.mcp_client)
        system = compose_system_prompt(domain_blocks, dynamic=dynamic)
        messages = [*lc_history(history), HumanMessage(content=question)]
        # 출력 안전 가드(canary·프롬프트유출·한자·욕설)는 LiteLLM 게이트웨이 SafetyGuard 가 스트리밍/비스트리밍 모두 담당
        # MCP 연결·에이전트 루프·스트림→SSE 매핑은 재사용 러너에 위임 (이 서비스는 포트폴리오 도메인 프롬프트·메시지만 구성)
        async for event in stream_mcp_agent(self.chat_client, self.mcp_client, system, messages):
            yield event
