"""`/chat/accounts`·`/chat/holders` ↔ portfolio-mcp 계약 대조 (#246 #368) — fail-closed.

## 왜 있나

`GET /chat/accounts` 가 400 을 냈다(#246). 원인은 소비자·생산자가 **같은 이름의 다른 모델**을
쓴 것이다(#368) — 소비자 `AccountInfo` 는 `name`(필수)·`kind`·`base_ccy` 를 기대했는데 생산자
portfolio-mcp 는 `account_name`·`account_type`·`base_currency` 를 내보낸다. 라우터에서
`AccountsOut(...)` 을 만드는 순간 pydantic `ValidationError`(=`ValueError`) → `handle_value_error`
→ 400 이었다.

그물이 이 축을 못 봤던 이유도 같다: `verify_chat_mcp_tool_error_status.py` 의 정상응답 대조군
fake 가 **소비자 스키마 모양을 지어낸 것**이라, 생산자가 무엇을 내보내든 항상 초록이었다.
그래서 이 스크립트는 fake 를 짓지 않고 **생산자의 pydantic 모델(portfolio-mcp
`schemas/portfolio/portfolio_schema.py`)을 그대로 import 해** 그 모델로 payload 를 만든다 —
생산자가 필드를 바꾸면 payload 생성 자체가 깨져 빨간불이 된다.

## 무엇을 대조하나

  (1) 생산자 모델로 만든 payload → `GET /chat/accounts` 200, 값이 매핑대로 실린다
      (account_name→name · account_type→kind · base_currency→base_ccy)
  (2) 소비자 뷰 모델(`ChatAccountInfo`)이 요구하는 필드가 전부 매핑표로 덮인다
      — 매핑 없는 필수 필드가 생기면 실패(다시 400 을 낼 자리)
  (3) 계좌주 축 — 생산자 모델에 계좌주 신원 필드(`holder`/`holder_email`)가 **없음**을 확인한다.
      생산자가 그 필드를 갖게 되면 이 검사가 빨간불로 "`/chat/holders` 배선을 갱신하라"고
      알린다. 없는 동안 `/chat/holders` 는 200 + 빈 목록이 정상 상태다(계좌 별칭을 사람 이름
      자리에 끼워 넣던 폴백은 #368 에서 제거)
  (4) 부정 통제 — 종전 소비자 스키마(`name` 필수)로는 같은 생산자 payload 가 실제로 깨진다는
      것을 보여준다. 이 스크립트가 무언가를 실제로 잡고 있다는 증거

검증 경계: 실제 MCP 왕복·portfolio-mcp 기동·DB 는 범위 밖이다. 확인 대상은 **필드명 계약**이다.

`uv run python scripts/verify_chat_portfolio_contract.py` (cwd=backend-service).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
for _key in (
    "BACKEND_SQL_DB_DRIVER",
    "BACKEND_SQL_DB_ODBC_DRIVER",
    "BACKEND_SQL_DB_HOST",
    "BACKEND_SQL_DB_NAME",
    "BACKEND_SQL_DB_USER",
    "BACKEND_SQL_DB_PASSWORD",
):
    os.environ.setdefault(_key, "x")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "1433")
for _key in ("SFTP_HOST", "SFTP_USERNAME", "SFTP_PASSWORD"):
    os.environ.setdefault(_key, "x")
os.environ.setdefault("SFTP_PORT", "22")

SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT / "app"))

PRODUCER_SCHEMA = REPO_ROOT / "portfolio-mcp-service" / "app" / "schemas" / "portfolio" / "portfolio_schema.py"


def _load_producer_schema():
    """생산자 스키마 모듈을 파일 경로로 직접 import.

    이름을 `_producer_portfolio_schema` 로 두는 이유: 이 프로세스의 `schemas` 패키지는
    backend-service 것이라 평범한 import 로는 소비자 모듈이 잡힌다 — 그러면 대조가 아니라
    자기 자신을 보는 셈이 된다.
    """
    if not PRODUCER_SCHEMA.exists():
        print(f"FAIL: 생산자 스키마를 찾지 못했다 — {PRODUCER_SCHEMA}")
        raise SystemExit(1)
    spec = importlib.util.spec_from_file_location("_producer_portfolio_schema", PRODUCER_SCHEMA)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


producer = _load_producer_schema()

import jwt as pyjwt  # noqa: E402
import routers.chat.chat_router as chat_router_module  # noqa: E402
from core.config import settings  # noqa: E402
from core.container import Container  # noqa: E402
from core.exception_handler import get_exception_handlers  # noqa: E402
from dependency_injector import providers  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel, ValidationError  # noqa: E402
from schemas.chat.chat_schema import ChatAccountInfo  # noqa: E402
from services.chat.portfolio_chat_service import HOLDER_EMAIL_FIELD, HOLDER_NAME_FIELD  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

# 소비자 뷰 모델 필드 → 생산자 필드. 매핑 정본은 `PortfolioChatService.list_accounts` 이고
# 여기는 그 매핑이 생산자 계약과 맞는지 확인하는 대조표다.
ACCOUNT_FIELD_MAP: dict[str, str] = {
    "account_id": "account_id",
    "name": "account_name",
    "kind": "account_type",
    "base_ccy": "base_currency",
}

# 생산자 모델의 필드를 **키워드로 명시해** 인스턴스를 만든다 — 생산자가 필드를 renames/삭제하면
# 여기서 TypeError/ValidationError 로 깨져 계약 변화가 조용히 지나가지 않는다.
PRODUCER_ACCOUNT_KWARGS: dict[str, object] = {
    "account_id": "ACC-1001",
    "account_no": "5012-01-[계좌번호 일부 가려짐]",
    "account_name": "종합매매계좌",
    "account_type": "cash",
    "base_currency": "KRW",
    "nav": 12_300_000.0,
    "nav_by_currency": {"KRW": 12_300_000.0},
    "nav_in_base": 12_300_000.0,
    "fx_rates_used": {},
    "unconverted_currencies": [],
    "cash_balance": 8_500_000.0,
}


class _LegacyAccountInfo(BaseModel):
    """#368 이전 소비자 스키마 — (4) 부정 통제용."""

    account_id: str
    name: str
    kind: str = ""
    base_ccy: str = ""


class _ListAccountsTool:
    name = "portfolio_list_accounts"

    def __init__(self, payload: dict):
        self._payload = payload

    async def ainvoke(self, args):
        return [{"type": "json", "json": self._payload}]


class _FakeMcpClient:
    def __init__(self, tools: list):
        self._tools = tools
        self.connections: dict = {}

    async def get_tools(self, *, server_name: str | None = None):
        return self._tools


def _build_client(payload: dict) -> TestClient:
    import clients.mcp.mcp_client as mcp_client_module

    mcp_client_module._cached_tools = None
    mcp_client_module._cached_instructions = None

    container = Container()
    container.mcp_client.override(providers.Object(_FakeMcpClient([_ListAccountsTool(payload)])))

    app = FastAPI(exception_handlers=get_exception_handlers())
    app.container = container
    app.include_router(chat_router_module.router)
    return TestClient(app, raise_server_exceptions=False)


def _auth_header() -> dict:
    payload = {"sub": "u1", "email": "u1@a.com", "exp": int(time.time()) + 60}
    return {"Authorization": f"Bearer {pyjwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')}"}


def main() -> int:
    settings.AUTH_DEV_BYPASS = False
    problems: list[str] = []
    checks = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not cond:
            problems.append(f"{name} — {detail}" if detail else name)

    producer_fields = set(producer.AccountInfo.model_fields)
    payload = producer.AccountsOut(
        items=[producer.AccountInfo(**PRODUCER_ACCOUNT_KWARGS)],
        total_count=1,
    ).model_dump()
    wire_fields = set(payload["items"][0])

    # (1) 생산자 payload → /chat/accounts 200 + 매핑대로 실림
    client = _build_client(payload)
    hdr = _auth_header()
    r = client.get("/chat/accounts", headers=hdr)
    check("생산자 payload → /chat/accounts 200", r.status_code == 200, f"실제 {r.status_code}: {r.text}")
    check("생산자 payload → 400 아님(#246 회귀)", r.status_code != 400, f"실제 {r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    item = (body.get("items") or [{}])[0]
    for consumer_field, producer_field in ACCOUNT_FIELD_MAP.items():
        check(
            f"매핑 {producer_field}→{consumer_field}",
            item.get(consumer_field) == PRODUCER_ACCOUNT_KWARGS[producer_field],
            f"기대 {PRODUCER_ACCOUNT_KWARGS[producer_field]!r}, 실제 {item.get(consumer_field)!r}",
        )

    # (2) 소비자 뷰 모델의 모든 필드가 매핑표로 덮이고, 매핑 대상이 생산자에 실재한다
    for consumer_field in ChatAccountInfo.model_fields:
        check(
            f"소비자 필드 {consumer_field} 에 매핑 있음",
            consumer_field in ACCOUNT_FIELD_MAP,
            "매핑 없는 필드는 400 을 다시 낼 자리다",
        )
    for producer_field in ACCOUNT_FIELD_MAP.values():
        check(
            f"매핑 대상 {producer_field} 이 생산자 계약에 실재",
            producer_field in producer_fields,
            f"생산자 필드: {sorted(producer_fields)}",
        )
        check(
            f"매핑 대상 {producer_field} 이 실제 payload 에도 실림",
            producer_field in wire_fields,
            f"payload 필드: {sorted(wire_fields)}",
        )

    # (3) 계좌주 축 — 생산자에 신원 필드가 없는 동안은 200 + 빈 목록이 정상이다
    r2 = client.get("/chat/holders", headers=hdr)
    check("/chat/holders 200", r2.status_code == 200, f"실제 {r2.status_code}: {r2.text}")
    check("/chat/holders 빈 목록", (r2.json() if r2.status_code == 200 else {}).get("items") == [], r2.text)
    for field in (HOLDER_NAME_FIELD, HOLDER_EMAIL_FIELD):
        check(
            f"생산자에 계좌주 필드 {field} 없음(있으면 /chat/holders 배선 갱신 필요)",
            field not in producer_fields,
            f"생산자가 {field} 를 갖게 됐다 — portfolio_chat_service.list_holders 를 실제 매핑으로 바꿔라 (#368)",
        )

    # (4) 부정 통제 — 종전 소비자 스키마는 같은 payload 에서 실제로 깨진다
    try:
        _LegacyAccountInfo(**payload["items"][0])
        legacy_broke = False
    except ValidationError:
        legacy_broke = True
    except TypeError:
        legacy_broke = True
    check(
        "부정 통제: 종전 스키마(name 필수)는 같은 payload 에서 ValidationError",
        legacy_broke,
        "이 검사가 아무것도 안 잡고 있다는 뜻이다",
    )

    if checks == 0:
        print("FAIL: 검사 0건 — 대조 대상이 없다")
        return 1
    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(
        f"PASS: /chat ↔ portfolio-mcp 계약 대조 {checks}건 "
        f"(생산자 필드 {len(producer_fields)}개 · 매핑 {len(ACCOUNT_FIELD_MAP)}쌍 · 요청 2건)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
