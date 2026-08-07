"""GET /chat/accounts·/chat/holders 의 MCP tool 실패 상태코드 회귀 검증 (#246).

배경: `GET /chat/accounts` 가 400 을 낸다는 결함이 보고됐다. 원인은 `call_mcp_tool`
(clients/mcp/mcp_client.py)이 "tool 을 못 찾음"·"응답 형식 이상" 같은 실패를 `ValueError` 로
던졌고, 전역 핸들러(`handle_value_error`)가 이를 400(BadRequestError, "네가 잘못 보냈다")으로
번역했기 때문이다. 그런데 `tool_name` 은 호출부(`portfolio_chat_service.py`)가 하드코딩한
값이라 사용자 입력이 끼어들 자리가 없다 — 이 실패는 **항상 서버측 원인**(MCP_SERVERS 미설정,
MCP 서버 다운, 응답 형식 이상)이지 클라이언트 잘못이 아니다. 실측: 로컬 dev 환경의
`backend-service/app/.env.development` 에 `MCP_SERVERS` 가 아예 없어(`.env.example` 에는 있음)
`MultiServerMCPClient.connections` 가 비고, tool 목록이 항상 빈 배열이 되어 이 분기로 떨어진다
— "통합 이전부터 있던 결함"이라는 이슈 진술과 정합(devactivity 시절부터 같은 env 공백이었을
공산이 크다). 이미 `stream_mcp_agent`(clients/mcp/mcp_agent.py)는 같은 부류의 실패를
`ServiceUnavailableError`(503)로 옮겨 놓았다 — `call_mcp_tool` 만 뒤처져 있었다.

계약 (fail-closed) — `call_mcp_tool`(mcp_client.py) 이 `ServiceUnavailableError` 를 던지는
raise 지점 4곳을 전부 커버한다(#357 리뷰 [I] — 이전엔 2곳만 커버하면서 "4개 시나리오"라고
적어 실제보다 넓게 읽혔다):
  (1) MCP tool 목록이 비어 대상 tool 을 못 찾음 → GET /chat/accounts, /chat/holders 모두 503
      (수정 전엔 400) — `matched is None`
  (2) tool 응답 content block 에 text/json 이 없음 → 503 (수정 전엔 400) — `_extract_payload`
  (2b) `ainvoke()` 가 list 가 아닌 값을 반환 → 503 — `call_mcp_tool` 자신의 `isinstance` 체크
  (2c) text 블록은 있으나 JSON 파싱 실패 → 503 — `_parse_json` 의 `JSONDecodeError`
  (3) 정상 응답(툴이 존재하고 형식이 맞음) → 200, 데이터 그대로 통과 (회귀 없음의 대조군)

검증 경계: 실제 MCP 왕복·DB 는 fake 로 대체 — 확인 대상은 `call_mcp_tool` 예외 타입 →
`core/exception_handler.py` → HTTP 상태코드로 이어지는 매핑 계약이다. 실제 MCP_SERVERS 배선·
portfolio-mcp 기동 실사는 범위 밖. **생산자와의 필드명 계약**도 이 스크립트 범위 밖이다 —
`verify_chat_portfolio_contract.py` 가 생산자 모델을 직접 import 해 담당한다 (#368).

pydantic·fastapi import 필요 — `uv run python scripts/verify_chat_mcp_tool_error_status.py`
(cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
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

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

import jwt as pyjwt  # noqa: E402
import routers.chat.chat_router as chat_router_module  # noqa: E402
from core.config import settings  # noqa: E402
from core.container import Container  # noqa: E402
from core.exception_handler import get_exception_handlers  # noqa: E402
from dependency_injector import providers  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class _ListAccountsTool:
    """정상 응답을 내는 portfolio_list_accounts 스텁 — **생산자 필드명**을 쓴다.

    종전 이 fake 는 소비자 스키마 모양(`name`/`kind`)을 지어낸 것이라 생산자가 무엇을 내보내든
    항상 초록이었다(#368). 생산자와의 필드명 대조 자체는
    `verify_chat_portfolio_contract.py` 가 생산자 모델을 import 해서 담당하고, 여기서는 그 모양이
    상태코드 매핑 경로를 통과한다는 것만 본다.
    """

    name = "portfolio_list_accounts"

    async def ainvoke(self, args):
        items = [
            {"account_id": "acct-1", "account_name": "종합매매계좌", "account_type": "cash", "base_currency": "KRW"}
        ]
        return [{"type": "json", "json": {"items": items, "total_count": len(items)}}]


class _MalformedTool:
    """content block 에 text/json 이 없는 응답 — 형식 오류 재현 (`_extract_payload` 의 raise)."""

    name = "portfolio_list_accounts"

    async def ainvoke(self, args):
        return [{"type": "image", "data": "..."}]


class _NonListResultTool:
    """`ainvoke()` 가 list 가 아닌 값을 돌려줌 — `call_mcp_tool` 자신의
    `not isinstance(result, list)` raise 를 재현 (#357 리뷰 [I] — 이전엔 이 지점이 미커버였다)."""

    name = "portfolio_list_accounts"

    async def ainvoke(self, args):
        return {"items": []}


class _UnparsableJsonTool:
    """text 블록이 있지만 JSON 으로 파싱되지 않음 — `_parse_json` 의 `JSONDecodeError` raise 를
    재현 (#357 리뷰 [I] — 이전엔 이 지점이 미커버였다)."""

    name = "portfolio_list_accounts"

    async def ainvoke(self, args):
        return [{"type": "text", "text": "{not valid json"}]


class FakeMcpClient:
    """MCP tool 목록을 그대로 돌려주는 스텁. `tools=[]` 면 "tool 못 찾음" 분기가 재현된다."""

    def __init__(self, tools: list):
        self._tools = tools
        self.connections: dict = {}

    async def get_tools(self, *, server_name: str | None = None):
        return self._tools


def _token(secret: str) -> str:
    payload = {"sub": "u1", "email": "u1@a.com", "exp": int(time.time()) + 60}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def build_client(fake_mcp: FakeMcpClient) -> TestClient:
    import clients.mcp.mcp_client as mcp_client_module

    # 모듈 전역 tool 캐시 초기화 — 이전 시나리오의 tool 목록이 새 FakeMcpClient 에 새지 않게.
    mcp_client_module._cached_tools = None
    mcp_client_module._cached_instructions = None

    container = Container()
    container.mcp_client.override(providers.Object(fake_mcp))

    app = FastAPI(exception_handlers=get_exception_handlers())
    app.container = container
    app.include_router(chat_router_module.router)
    return TestClient(app, raise_server_exceptions=False)


def main() -> int:
    settings.AUTH_DEV_BYPASS = False
    secret = settings.JWT_SECRET
    tok = _hdr(_token(secret))

    problems: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            problems.append(f"{name} — {detail}" if detail else name)

    # (1) MCP tool 목록이 빈 상태(MCP_SERVERS 미설정과 동형) — 400 이 아니라 503 이어야 한다.
    empty_client = build_client(FakeMcpClient(tools=[]))
    r = empty_client.get("/chat/accounts", headers=tok)
    check("tool 못 찾음 → /chat/accounts 503", r.status_code == 503, f"실제 {r.status_code}: {r.text}")
    check("tool 못 찾음 → 400 아님(회귀 없음)", r.status_code != 400, f"실제 {r.status_code}")

    r2 = empty_client.get("/chat/holders", headers=tok)
    check("tool 못 찾음 → /chat/holders 503", r2.status_code == 503, f"실제 {r2.status_code}: {r2.text}")

    # (2) tool 은 있으나 응답 형식이 기대와 다름(text/json 블록 없음, `_extract_payload` raise) — 503.
    malformed_client = build_client(FakeMcpClient(tools=[_MalformedTool()]))
    r3 = malformed_client.get("/chat/accounts", headers=tok)
    check("응답 형식 오류(블록 없음) → 503", r3.status_code == 503, f"실제 {r3.status_code}: {r3.text}")

    # (2b) `ainvoke()` 가 list 가 아닌 값을 반환 — `call_mcp_tool` 자신의 raise, (2)와 다른 지점.
    non_list_client = build_client(FakeMcpClient(tools=[_NonListResultTool()]))
    r3b = non_list_client.get("/chat/accounts", headers=tok)
    check("응답 형식 오류(list 아님) → 503", r3b.status_code == 503, f"실제 {r3b.status_code}: {r3b.text}")

    # (2c) text 블록은 있으나 JSON 파싱 실패 — `_parse_json` 의 raise, (2)·(2b)와 다른 지점.
    unparsable_client = build_client(FakeMcpClient(tools=[_UnparsableJsonTool()]))
    r3c = unparsable_client.get("/chat/accounts", headers=tok)
    check("응답 형식 오류(JSON 파싱 실패) → 503", r3c.status_code == 503, f"실제 {r3c.status_code}: {r3c.text}")

    # (3) 정상 tool — 200 + 데이터 통과 (수정이 정상 경로를 깨지 않았는지 대조군).
    ok_client = build_client(FakeMcpClient(tools=[_ListAccountsTool()]))
    r4 = ok_client.get("/chat/accounts", headers=tok)
    check("정상 tool → 200", r4.status_code == 200, f"실제 {r4.status_code}: {r4.text}")
    body = r4.json() if r4.status_code == 200 else {}
    check(
        "정상 tool → 데이터 통과",
        body.get("total_count") == 1 and body.get("items", [{}])[0].get("account_id") == "acct-1",
        str(body),
    )

    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("PASS: chat MCP tool 실패가 400 대신 503 으로 매핑됨 (raise 지점 4곳 · 요청 6건 검사)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
