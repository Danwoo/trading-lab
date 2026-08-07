"""주간 활동요약 ↔ portfolio-mcp account-activity tool 계약 회귀 검증 (#114).

배경: 주간 활동요약이 단일 계좌 tool `portfolio_get_account_activity` 에 존재하지 않는
`account_ids`(복수) 인자를 보내고 필수 `account_id`(단수)는 보내지 않아 매주 스키마 거부 →
조용히 "활동 없음" 메일로 끝났다. 응답 소비부도 실제 계약(`events` 의 date/detail)과 불일치해
인자만 고쳐도 빈 결과가 유지되는 이중 결함. 계좌당 개별 호출 + events 소비 + found=False
표면화로 수정했고, 이 스크립트가 그 계약을 실제 portfolio-mcp 스키마로 재현한다.

계약:
  (1) 호출 형태 — 주차 × 유니크 계좌당 1회, 인자가 실제 AccountActivityIn 스키마를 통과
  (2) 소비 — 응답 events 의 활동(date/detail)이 요약을 거쳐 발송 메일 HTML 에 도달
  (3) found=False — '활동 0건' 과 구분된 계좌 미확인 메시지로 표면화(실행당 계좌별 1회), 메일 미발송
  (4) 회귀 네거티브 — 구 인자 형태(account_ids 리스트)는 스키마가 거부 (missing account_id)
  (5) 동일 email 다계좌 — 주차당 섹션 1개로 병합, 두 계좌 그룹 공존 + 중복 멤버 행 무해
  (6) 부분 실패 — 한 계좌 조회 예외가 같은 주차의 다른 계좌·다음 주차를 막지 않음

검증 경계: MCP 왕복·LLM·SMTP 는 fake 로 대체 — fake tool 이 인자를 **실제 portfolio-mcp
pydantic 스키마**(importlib 파일 로드, 로컬 복사본 아님 — 서버 스키마가 바뀌면 여기가 깨진다)로
검증하고 실제 Out 스키마로 응답을 조립하므로, 확인 대상은 devactivity 소비 코드 ↔ 스키마 계약이다.
streamable-http 전송·LLM 요약 품질·SMTP 발송은 범위 밖 (dev 기동 실사 대상).

pydantic·langchain import 필요 — `uv run python scripts/verify_activity_report.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
# core.config Settings 필수 필드 (DB 는 사용하지 않으므로 값은 더미)
for key in (
    "BACKEND_SQL_DB_DRIVER",
    "BACKEND_SQL_DB_ODBC_DRIVER",
    "BACKEND_SQL_DB_HOST",
    "BACKEND_SQL_DB_NAME",
    "BACKEND_SQL_DB_USER",
    "BACKEND_SQL_DB_PASSWORD",
):
    os.environ.setdefault(key, "x")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "1433")
for key in ("SFTP_HOST", "SFTP_USERNAME", "SFTP_PASSWORD"):
    os.environ.setdefault(key, "x")
os.environ.setdefault("SFTP_PORT", "22")

SERVICE_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = SERVICE_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

PMCP_SCHEMA_PATH = (
    SERVICE_ROOT.parent / "portfolio-mcp-service" / "app" / "schemas" / "portfolio" / "portfolio_schema.py"
)
_spec = importlib.util.spec_from_file_location("pmcp_portfolio_schema", PMCP_SCHEMA_PATH)
_pmcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pmcp)
AccountActivityIn = _pmcp.AccountActivityIn
AccountActivityOut = _pmcp.AccountActivityOut
ActivityLine = _pmcp.ActivityLine

import services.report.activity_report_service as ars_module  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from schemas.report.report_schema import ActivitySummaries, PortfolioSummary  # noqa: E402
from services.report.activity_report_service import ActivityReportService  # noqa: E402

SINCE = datetime(2026, 7, 6, 9, 0)
UNTIL = datetime(2026, 7, 20, 9, 0)  # 2주
PERIOD = "2026-07-06 ~ 2026-07-20"

MISSING_ACCOUNT = "ACC-OTHER"  # 미존재/타 테넌트 → found=False
BROKEN_ACCOUNT = "ACC-BOOM"  # 전송 장애 → 예외

EVENTS: dict[tuple[str, int], list[dict]] = {
    ("ACC-A1", 0): [
        {
            "date": "2026-07-07",
            "action": "trade",
            "detail": "trade 삼성전자 10주 (+1,000,000 KRW)",
            "amount": 1000000.0,
        },
    ],
    ("ACC-A1", 1): [
        {
            "date": "2026-07-14",
            "action": "dividend",
            "detail": "dividend 삼성전자 배당 (+35,000 KRW)",
            "amount": 35000.0,
        },
    ],
    ("ACC-A2", 0): [
        {"date": "2026-07-08", "action": "cash", "detail": "deposit 입금 (+500,000 KRW)", "amount": 500000.0},
    ],
}

MEMBERS = [
    {"account_id": "ACC-A1", "email": "alice@example.com", "name": "앨리스"},
    {"account_id": "ACC-A2", "email": "alice@example.com", "name": "앨리스"},
    {"account_id": "ACC-A1", "email": "alice@example.com", "name": "앨리스"},  # 중복 행
    {"account_id": MISSING_ACCOUNT, "email": "bob@example.com", "name": "밥"},
    {"account_id": BROKEN_ACCOUNT, "email": "carol@example.com", "name": "캐럴"},
]

calls: list[dict] = []
schema_violations: list[str] = []


async def fake_call_mcp_tool(client, tool_name: str, tool_args: dict | None = None) -> dict:
    calls.append({"tool": tool_name, "args": dict(tool_args or {})})
    if tool_name != "portfolio_get_account_activity":
        schema_violations.append(f"예상 밖 tool 호출: {tool_name}")
        raise ValueError(f"unknown tool: {tool_name}")
    try:
        body = AccountActivityIn(**(tool_args or {}))
    except ValidationError as e:
        schema_violations.append(f"AccountActivityIn 거부: {tool_args} — {e.errors(include_url=False)}")
        raise
    if body.account_id == BROKEN_ACCOUNT:
        raise RuntimeError("connection reset")
    week = (datetime.fromisoformat(body.since) - SINCE).days // 7
    if body.account_id == MISSING_ACCOUNT:
        out = AccountActivityOut(account_id=body.account_id, events=[], count=0, found=False, period=PERIOD)
    else:
        events = [ActivityLine(**e) for e in EVENTS.get((body.account_id, week), [])]
        out = AccountActivityOut(
            account_id=body.account_id, events=events, count=len(events), found=True, period=PERIOD
        )
    return out.model_dump()


class FakeStructuredLLM:
    """요약 프롬프트의 [그룹] 블록을 그대로 구조화 출력으로 되돌리는 패스스루."""

    async def ainvoke(self, messages) -> ActivitySummaries:
        blocks = messages[-1].content.split("\n\n")
        summaries = []
        for block in blocks:
            lines = block.splitlines()
            portfolio = lines[0].strip("[]")
            items = [ln[2:] for ln in lines[1:] if ln.startswith("- ")]
            summaries.append(PortfolioSummary(portfolio=portfolio, items=items))
        return ActivitySummaries(summaries=summaries)


class FakeSummarizeClient:
    def with_structured_output(self, schema) -> FakeStructuredLLM:
        return FakeStructuredLLM()


class FakeMailClient:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    async def send_html(self, to: str, subject: str, html: str) -> None:
        self.sent.append((to, subject, html))


def main() -> int:
    problems: list[str] = []

    def check(name: str, ok: bool) -> None:
        if not ok:
            problems.append(name)

    ars_module.call_mcp_tool = fake_call_mcp_tool
    mail = FakeMailClient()
    service = ActivityReportService(
        mcp_client=object(),  # fake call_mcp_tool 만 거치므로 미사용 센티널
        summarize_client=FakeSummarizeClient(),
        mail_client=mail,
    )

    async def run() -> list[str]:
        return [msg async for msg in service.generate_for(MEMBERS, SINCE, UNTIL)]

    msgs = asyncio.run(run())

    # (1) 호출 형태 — 2주 × 유니크 계좌 4개 = 8회, 전부 실스키마 통과, 구 인자(account_ids) 없음
    check("스키마 위반 없음", not schema_violations)
    check("호출 수 = 주차 × 유니크 계좌 (8회)", len(calls) == 8)
    called = {(c["args"].get("account_id"), c["args"].get("since")) for c in calls}
    check("계좌×주차 조합이 각 1회", len(called) == len(calls))
    check("account_ids(복수) 인자 미사용", all("account_ids" not in c["args"] for c in calls))

    # (2) 소비 — events 의 date/detail 이 메일 HTML 에 도달
    sent_to = {to for to, _, _ in mail.sent}
    alice_html = next((h for to, _, h in mail.sent if to == "alice@example.com"), "")
    check("alice 메일 발송됨", "alice@example.com" in sent_to)
    check("1주차 trade detail 도달", "trade 삼성전자 10주 (+1,000,000 KRW)" in alice_html)
    check("2주차 dividend detail 도달", "dividend 삼성전자 배당 (+35,000 KRW)" in alice_html)
    check("event date 도달", "2026-07-07" in alice_html)
    check("주차 섹션 2개 (1·2주차)", "1주차" in alice_html and "2주차" in alice_html)

    # (3) found=False — 구분 메시지 1회 + 메일 미발송 ('활동 0건' 처럼 조용히 넘어가지 않음)
    missing_msgs = [m for m in msgs if m.startswith(f"계좌 미확인 — {MISSING_ACCOUNT}")]
    check("계좌 미확인 메시지 실행당 1회", len(missing_msgs) == 1)
    check("bob 메일 미발송", "bob@example.com" not in sent_to)
    check("bob 활동 없음 처리", any(m.startswith("bob@example.com: 해당 기간 활동 없음") for m in msgs))

    # (4) 회귀 네거티브 — 구 인자 형태는 실스키마가 거부 (missing account_id)
    old_args = {"since": SINCE.isoformat(), "until": UNTIL.isoformat(), "account_ids": ["ACC-A1", "ACC-A2"]}
    try:
        AccountActivityIn(**old_args)
        check("구 인자 형태 거부됨", False)
    except ValidationError as e:
        errors = e.errors(include_url=False)
        check(
            "구 인자 형태 거부됨 (account_id missing)",
            any(err["loc"] == ("account_id",) and err["type"] == "missing" for err in errors),
        )

    # (5) 동일 email 다계좌 — 한 섹션에 두 계좌 그룹 병합, 중복 멤버 행은 라인 중복 없음
    check("두 계좌 그룹 공존", "ACC-A1" in alice_html and "ACC-A2" in alice_html)
    check("주차당 섹션 1개 (1주차 중복 없음)", alice_html.count("1주차") == 1)
    check("중복 멤버 행 라인 중복 없음", alice_html.count("trade 삼성전자 10주") == 1)

    # (6) 부분 실패 — BROKEN 계좌 예외가 주차마다 격리되고 나머지 진행 (alice 발송은 (2) 에서 확인)
    broken_fail_msgs = [m for m in msgs if f"계좌 {BROKEN_ACCOUNT} 조회 실패" in m]
    check("실패 계좌 주차별 재시도 (2회 격리)", len(broken_fail_msgs) == 2)
    check("carol 활동 없음 처리", any(m.startswith("carol@example.com: 해당 기간 활동 없음") for m in msgs))
    check("carol 메일 미발송", "carol@example.com" not in sent_to)

    if problems:
        print("활동요약 계약 검증 실패:")
        for p in problems:
            print(f"  ✗ {p}")
        if schema_violations:
            print("스키마 위반 상세:")
            for v in schema_violations:
                print(f"  ! {v}")
        return 1
    print("활동요약 계약 검증 통과 — 계좌당 개별 호출(실스키마)·events 소비·found=False 표면화·부분 실패 격리 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
