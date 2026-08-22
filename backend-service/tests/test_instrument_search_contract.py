"""종목 마스터 검색의 계약 — DB 없이 잡히는 것들 (#318).

DB 앞에 세워야만 보이는 것(LIKE 이스케이프가 실제로 먹는가·정렬 순서)은
`scripts/verify_instrument_search.py` 가 진짜 Postgres 에서 확인한다. 여기는 **DB 없이도
매번 도는** 축을 진다:

  ① 조회 상한 — 4,303행을 통째로 내려보낼 수 있는 입력이 없다 (기본값·상한·거절)
  ② 「없음」과 「아직 안 받음」을 가르는 판정이 **결과가 0건일 때만** 마스터를 묻는다
  ③ 페이지네이션 (anti-patterns 룰 6) — `ROW_NUMBER()` + skip/take 가 SQL 에 있다
  ④ LIKE 특수문자를 이스케이프한 패턴으로 바인딩한다 (`_` 한 글자가 전 종목을 훑지 않는다)
  ⑤ 라우트 lockstep — backend prefix 를 프론트 프록시·서비스가 byte-identical 로 복제한다

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_instrument_search_contract.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_APP_DIR = _REPO / "backend-service" / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exceptions import BadRequestError  # noqa: E402
from repositories.instrument.instrument_repository import InstrumentRepository  # noqa: E402
from services.instrument.instrument_service import MAX_TAKE, InstrumentService  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class FakeRepository:
    """호출을 기록하는 대역. 「몇 건을 요청했나」·「마스터를 물었나」가 검사 대상이다."""

    def __init__(self, rows: list[dict], has_any: bool = True):
        self.rows = rows
        self.has_any = has_any
        self.calls: list[dict] = []
        self.has_any_calls = 0

    def select_instrument_list(self, args: dict):
        self.calls.append(args)
        return self.rows, len(self.rows)

    def has_any_instrument(self) -> bool:
        self.has_any_calls += 1
        return self.has_any


ROW = {
    "country": "KR",
    "market": "KOSPI",
    "symbol": "005930",
    "issuer_nm": "삼성전자",
    "currency": "KRW",
    "is_active": "Y",
}


def check_take_bounds() -> None:
    repository = FakeRepository([ROW])
    service = InstrumentService(instrument_repository=repository)

    service.select_instrument_list({"q": "삼성"})
    check("take 를 안 주면 기본값을 쓴다", repository.calls[-1]["take"], 20)
    check("기본값이 상한 안이다", repository.calls[-1]["take"] <= MAX_TAKE, True)

    service.select_instrument_list({"q": "삼성", "take": MAX_TAKE})
    check("상한값은 통과한다", repository.calls[-1]["take"], MAX_TAKE)

    for bad in (MAX_TAKE + 1, 0, -1, 10_000):
        try:
            service.select_instrument_list({"q": "삼성", "take": bad})
            check(f"take={bad} 를 거절한다", "통과됨", "BadRequestError")
        except BadRequestError:
            check(f"take={bad} 를 거절한다", "BadRequestError", "BadRequestError")

    try:
        service.select_instrument_list({"q": "삼성", "skip": -1})
        check("음수 skip 을 거절한다", "통과됨", "BadRequestError")
    except BadRequestError:
        check("음수 skip 을 거절한다", "BadRequestError", "BadRequestError")


def check_empty_verdict() -> None:
    loaded = FakeRepository([], has_any=True)
    result = InstrumentService(instrument_repository=loaded).select_instrument_list({"q": "없는이름"})
    check("마스터가 찼으면 사유를 안 붙인다", result["unavailable_reason"], None)
    check("0건일 때는 마스터를 묻는다", loaded.has_any_calls, 1)

    empty = FakeRepository([], has_any=False)
    result = InstrumentService(instrument_repository=empty).select_instrument_list({"q": "삼성"})
    reason = result["unavailable_reason"] or ""
    check("빈 마스터 — 아직 안 받았다고 답한다", "아직 한 번도 받지 않았습니다" in reason, True)
    check("빈 마스터 — 다음 걸음을 말한다", "적재" in reason, True)
    check("빈 마스터 — 「없는 종목」이라 단정하지 않는다", "없는 종목" in reason, False)

    found = FakeRepository([ROW], has_any=False)
    result = InstrumentService(instrument_repository=found).select_instrument_list({"q": "삼성"})
    check("결과가 있으면 마스터를 묻지 않는다", found.has_any_calls, 0)
    check("결과가 있으면 사유가 없다", result["unavailable_reason"], None)


def check_pagination_sql() -> None:
    source = (_APP_DIR / "repositories" / "instrument" / "instrument_repository.py").read_text(encoding="utf-8")
    check("ROW_NUMBER() 로 자른다 (룰 6)", "ROW_NUMBER() OVER" in source, True)
    check("skip/take 로 구간을 잡는다", "rn BETWEEN" in source, True)
    check("전체 건수를 따로 센다", "COUNT(*)" in source, True)


def check_like_escaping() -> None:
    where, params = InstrumentRepository._where({"q": "50_%"})
    check("이스케이프 절을 붙인다", "ESCAPE" in where, True)
    check("특수문자를 글자로 바꿔 바인딩한다", params["pattern"], "%50\\_\\%%")
    check("코드와 종목명 양쪽에 건다", where.count(":pattern"), 2)

    _, order_params = InstrumentRepository._order_by({"q": "50_%"})
    check("정렬 패턴도 이스케이프한다", order_params["prefix"], "50\\_\\%%")

    where, params = InstrumentRepository._where({})
    check("검색어가 없으면 패턴을 안 건다", "pattern" in params, False)
    check(
        "검색어가 없어도 시장 조건은 따로 걸린다",
        ":market" in InstrumentRepository._where({"market": "KOSPI"})[0],
        True,
    )


def check_route_lockstep() -> None:
    router = (_APP_DIR / "routers" / "instrument" / "instrument_router.py").read_text(encoding="utf-8")
    match = re.search(r'APIRouter\(prefix="([^"]+)"', router)
    prefix = match.group(1) if match else "<없음>"
    check("backend prefix", prefix, "/instrument")

    proxy = (_REPO / "frontend" / "app" / "api" / "external" / "backend" / "instrument" / "route.ts").read_text(
        encoding="utf-8"
    )
    check("프론트 프록시가 prefix 를 그대로 복제한다", f'BACKEND_SERVICE_URL + "{prefix}"' in proxy, True)

    service = (_REPO / "frontend" / "services" / "terminal" / "instrumentService.ts").read_text(encoding="utf-8")
    check("서비스가 그 프록시 경로를 부른다", f'"/api/external/backend{prefix}"' in service, True)
    # 서버 실패를 「검색 결과 없음」으로 뭉개지 않는다 — 이 옵션이 빠지면 화면이 다시 거짓말한다.
    check("실패를 예외로 받는다", "throwOnFailure: true" in service, True)


def main() -> int:
    check_take_bounds()
    check_empty_verdict()
    check_pagination_sql()
    check_like_escaping()
    check_route_lockstep()

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 25:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 조회 상한·빈 마스터 판정·페이지네이션·LIKE 이스케이프·라우트 lockstep 이 서 있다 (#318)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
