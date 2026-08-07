"""포트폴리오 활동 요약 서비스 — 계좌 활동 수집 → LLM 요약 → 메일 발송."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

from clients.mail.mail_client import MailClient
from clients.mcp.mcp_client import call_mcp_tool
from core.logger import logger
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from schemas.report.report_schema import ActivitySummaries
from utils.common.time_utils import now_kst
from utils.report.report_utils import collect, dedupe_common, render_html

_SYSTEM_PROMPT = (
    "투자 리서치 애널리스트로서 한 기간의 계좌·포트폴리오 활동 내역을 간결한 활동 요약으로 압축한다. "
    "중복·연속된 동일 종목 매매·유사 거래는 하나의 상위 활동 항목으로 적극 병합한다. "
    "개별 거래를 그대로 나열하지 말고, 큰 단위의 '무엇이 일어났는가'(신규 편입/비중 조정/배당·이자/리밸런싱) 중심으로 요약한다. "
    "포트폴리오당 3~6개 항목으로 간결하게(최대 7개). 성격이 다른 활동(매수/매도/배당/입출금/평가)만 구분한다. "
    "모든 수치는 제공된 활동 내역에만 근거하고 임의로 지어내지 않는다. 투자 조언·매매 권유 표현은 쓰지 않는다. "
    "포트폴리오명에 대괄호 등 입력 포맷 기호를 포함하지 않는다. "
    "입력 순서(오래된 것 → 최신) 유지. 한국어만 사용, 한자 금지."
)


class ActivityReportService:
    """기간 내 계좌 활동을 계좌별로 모아 LLM 으로 압축, 각 계좌주에게 메일 발송."""

    def __init__(
        self,
        mcp_client: MultiServerMCPClient,
        summarize_client: ChatOpenAI,
        mail_client: MailClient,
    ):
        self.mcp_client = mcp_client
        self._structured = summarize_client.with_structured_output(ActivitySummaries)
        self.mail_client = mail_client

    async def generate_for(self, members: list[dict], since: datetime, until: datetime) -> AsyncGenerator[str, None]:
        """멤버에게 [since, until] 요약 발송. 주별·계좌별 조회 후 멤버당 주차별 섹션을 한 통에 묶어 발송."""
        weeks = max(1, (until - since).days // 7)
        period = f"{since:%Y-%m-%d} ~ {until:%Y-%m-%d}"
        yield f"집계 기간: {period} ({weeks}주)"
        if not members:
            yield "발송 대상이 없습니다."
            return

        # tool 은 단일 계좌 계약(account_id) — 유니크 계좌당 1회 호출하고 공유 멤버는 결과 재사용
        account_ids = list(dict.fromkeys(m["account_id"] for m in members))
        by_email: dict[str, list[dict]] = {}
        for m in members:
            entries = by_email.setdefault(m["email"], [])
            if all(e["account_id"] != m["account_id"] for e in entries):
                entries.append(m)

        sections: dict[str, list[tuple[str, ActivitySummaries]]] = {email: [] for email in by_email}
        missing_reported: set[str] = set()
        for w in range(weeks):
            ws = since + timedelta(weeks=w)
            label = f"{w + 1}주차 ({ws:%m-%d} ~ {(ws + timedelta(days=6)):%m-%d})"
            yield f"{label} 활동 조회 중..."
            week_events: dict[str, list[dict]] = {}
            for account_id in account_ids:
                try:
                    result = await call_mcp_tool(
                        self.mcp_client,
                        "portfolio_get_account_activity",
                        {
                            "account_id": account_id,
                            "since": ws.isoformat(),
                            "until": (ws + timedelta(weeks=1)).isoformat(),
                        },
                    )
                except Exception as e:
                    logger.warning("[활동요약] %s 계좌 %s 조회 실패 — %s", label, account_id, e)
                    yield f"{label} 계좌 {account_id} 조회 실패 — {e}"
                    continue
                if not result.get("found"):
                    # 미존재와 타 테넌트 소유 모두 found=False (존재 오라클 차단) — '활동 0건' 과 구분해 표면화
                    if account_id not in missing_reported:
                        missing_reported.add(account_id)
                        logger.warning("[활동요약] 계좌 미확인 — %s (미존재 또는 타 테넌트 소유)", account_id)
                        yield f"계좌 미확인 — {account_id}: 미존재 또는 타 테넌트 소유, 멤버 등록 정보 확인 필요"
                    continue
                if result.get("truncated"):
                    logger.warning("[활동요약] %s 계좌 %s 활동이 최대 건수를 초과해 잘림", label, account_id)
                week_events[account_id] = result.get("events", [])

            for email, email_members in by_email.items():
                by_portfolio: dict[str, list[str]] = {}
                for member in email_members:
                    account_id = member["account_id"]
                    for group, lines in collect(week_events.get(account_id, []), account_id).items():
                        by_portfolio.setdefault(group, []).extend(lines)
                by_portfolio = dedupe_common(by_portfolio)
                if not by_portfolio:
                    continue
                try:
                    summaries = await self._summarize(by_portfolio)
                    sections[email].append((label, summaries))
                except Exception as e:
                    logger.warning("[활동요약] %s %s 요약 실패 — %s", email, label, e)
                    yield f"{email}: {label} 요약 실패 — {e}"

        for email, weekly in sections.items():
            if not weekly:
                yield f"{email}: 해당 기간 활동 없음 — 생략"
                continue
            try:
                await self.mail_client.send_html(
                    email,
                    f"[포트폴리오 활동 요약] {period}",
                    render_html(period, weekly),
                )
                yield f"{email}: 섹션 {len(weekly)}개 발송 완료"
            except Exception as e:
                logger.warning("[활동요약] %s 발송 실패 — %s", email, e)
                yield f"{email}: 발송 실패 — {e}"

        yield "전체 완료"

    @staticmethod
    def period(weeks: int) -> tuple[datetime, datetime]:
        """직전 N주 (정확히 N주 전 같은 요일·시각 ~ 현재, KST)."""
        until = now_kst()
        return until - timedelta(weeks=weeks), until

    async def _summarize(self, by_portfolio: dict[str, list[str]]) -> ActivitySummaries:
        blocks = "\n\n".join(f"[{p}]\n" + "\n".join(f"- {s}" for s in subs) for p, subs in by_portfolio.items())
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=blocks),
        ]
        return await self._structured.ainvoke(messages)
