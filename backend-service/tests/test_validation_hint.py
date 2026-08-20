"""422 가 **무엇을 넣어야 하는지** 말하는가 (DB·네트워크 없음, TestClient 로 실제 앱을 태운다).

`{"detail":[{"msg":"Field required","loc":["body","scope"]}]}` 만으로는 다음 수를 알 수 없다.
특히 `scope` 는 시장과 종목을 **한 문자열에** 합치는 형식이라 자연스러운 추측(`market`/`symbol`
분리)과 어긋난다 — 실제로 두 번 틀렸다(#253).

이 그물이 잠그는 것:

  ① 모델에 적힌 `description` 이 422 응답까지 실린다
  ② 설명이 없는 필드는 조용히 아무것도 안 붙인다 (없는 안내를 지어내지 않는다)
  ③ 적재 요청 필드들에 실제로 설명이 달려 있다 — 안내의 원천이 비면 ①이 무의미하다
  ④ 안내 문구가 형식의 두 갈래를 다 말한다 (시장 하나 / 시장:종목)
  ⑤ 값의 **범위**를 어긴 것도 안내를 받는다 — 빠뜨린 필드만 잡히면 절반이다 (#292)

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_validation_hint.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "validation-hint-test"
for _name, _value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(_name, _value)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exception_handler import get_exception_handlers  # noqa: E402
from fastapi import Body, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from schemas.backtest.backtest_schema import BacktestGridIn  # noqa: E402
from schemas.ingest.ingest_schema import IngestRunCreateIn  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class WithHint(BaseModel):
    described: str = Field(..., description="이 값은 이렇게 넣습니다")
    bare: str


def build_client() -> TestClient:
    """진짜 핸들러 등록 경로를 그대로 태운다 — 앱을 통째로 띄우지 않고 같은 배선만 재현한다."""
    app = FastAPI(exception_handlers=get_exception_handlers())

    @app.post("/described")
    def _described(body: WithHint = Body(...)):  # noqa: ARG001
        return {}

    @app.post("/ingest-run")
    def _ingest(body: IngestRunCreateIn = Body(...)):  # noqa: ARG001
        return {}

    @app.post("/backtest-run/grid")
    def _grid(body: BacktestGridIn = Body(...)):  # noqa: ARG001
        return {}

    return TestClient(app)


def main() -> int:
    client = build_client()

    # ① 설명이 있는 필드는 안내가 붙는다 / ② 없는 필드는 안 붙는다
    response = client.post("/described", json={})
    check("422 로 답한다", response.status_code, 422)
    by_field = {tuple(item["loc"]): item for item in response.json()["detail"]}
    check("설명 있는 필드에 안내가 붙는다", by_field[("body", "described")].get("hint"), "이 값은 이렇게 넣습니다")
    check("설명 없는 필드엔 안 붙는다", "hint" in by_field[("body", "bare")], False)

    # ④ 적재 요청 — 이슈 #253 이 실제로 보낸 본문 그대로
    wrong = {
        "source": "sample",
        "job_kind": "daily_bar",
        "market": "KR",
        "symbol": "SAMPLE001",
        "date_from": "2026-01-01",
        "date_to": "2026-08-14",
    }
    response = client.post("/ingest-run", json=wrong)
    check("적재 오요청이 422 다", response.status_code, 422)
    items = response.json()["detail"]
    scope_error = next((item for item in items if item["loc"] == ["body", "scope"]), None)
    check("scope 오류가 있다", scope_error is not None, True)
    hint = (scope_error or {}).get("hint", "")
    check("안내가 붙는다", bool(hint), True)
    check("시장 하나 형식을 말한다", "instrument_master" in hint, True)
    check("시장:종목 형식을 말한다", ":" in hint and "KOSPI:005930" in hint, True)
    check("틀린 축을 바로잡는다", "market" in hint and "따로 보내는 필드는 없습니다" in hint, True)

    # ⑤ 범위 위반 — 이슈 #292 가 실제로 보낸 본문. 필드는 다 있고 값 하나가 범위를 벗어났다.
    response = client.post(
        "/backtest-run/grid",
        json={
            "strategy_key": "sma_cross",
            "params": {},
            "market": "KOSPI",
            "symbol": "005930",
            "period_from": "2020-01-01",
            "period_to": "2020-12-31",
            "initial_cash": 0,
            "sweep": {"fast": [5, 10]},
        },
    )
    check("범위 위반이 422 다", response.status_code, 422)
    cash_error = next((item for item in response.json()["detail"] if item["loc"] == ["body", "initial_cash"]), None)
    check("initial_cash 오류가 있다", cash_error is not None, True)
    cash_hint = (cash_error or {}).get("hint", "")
    check("범위 위반에도 안내가 붙는다", bool(cash_hint), True)
    check("무엇이 유효한지 한국어로 말한다", "0 보다 커야" in cash_hint, True)

    # ③ 안내의 원천 — 필드들에 설명이 실제로 달려 있다 (0건이면 ①이 무의미하다)
    described = [name for name, field in IngestRunCreateIn.model_fields.items() if field.description]
    check("적재 요청 필드에 설명이 달려 있다", len(described), len(IngestRunCreateIn.model_fields))

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (적재 요청 필드 {len(described)}개에 설명)")
    if CHECKED < 10:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 422 가 무엇을 넣어야 하는지 말한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
