"""#243 — `market_ohlc` 최신순 1~120 계약이 깨지지 않았는지 (fail-closed).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_market_ohlc_contract.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

#243 은 "기간 지정 조회를 추가해야 한다"고 적었고, 설계(`시세적재-구현설계.md` §5.3)는 그것을
**기존 MCP 도구를 확장하는 방식이 아니라 별도 계약으로** 푼다 — `market_ohlc` 는 LLM 컨텍스트
보호가 목적이라 최신순 N개(1~120)로 그대로 두고, 기간 지정은 backend-service 의 `GET /bar/daily`
가 맡는다. 두 계약은 섞지 않는다.

그 결정은 "아무것도 안 했다"와 겉보기가 같다. 그래서 **안 바뀌었다는 것 자체를 검사**한다:
`count` 의 경계(ge=1, le=120)와 `interval` 의 닫힌 집합, 그리고 이 tool 을 바인딩하는 소비자
목록이 그대로인지. 누군가 나중에 "적재용으로도 쓰자"며 상한을 올리면 여기서 걸린다.

**fail-closed**: 대상 파일이 없거나 소비자를 0건 수집하면 실패한다. 검사한 개수를 출력에 남긴다.

파일 정적 검사라 서비스 앱을 import 하지 않는다 — 소비자(multi-agent-service)까지 함께 보므로
레포 루트를 기준으로 경로를 푼다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCHEMA_PATH = _REPO_ROOT / "market-data-mcp-service/app/schemas/market/market_schema.py"
_ROUTER_PATH = _REPO_ROOT / "market-data-mcp-service/app/routers/market/market_router.py"

# 이 tool 을 바인딩하는 소비자 — multi-agent 의 sub-agent 정의(operation_id 와 이름 결합, lockstep).
_CONSUMER_PATHS = (
    "multi-agent-service/app/agents/domains/risk.py",
    "multi-agent-service/app/agents/domains/instrument.py",
    "multi-agent-service/app/utils/agent/example_ai_events.py",
)

# 계약 값 — 이 숫자가 곧 "LLM 컨텍스트 보호"의 크기다.
_EXPECTED_MIN = 1
_EXPECTED_MAX = 120
_EXPECTED_INTERVALS = ("1d", "1w", "1mo")


def test_market_ohlc_contract_unchanged() -> int:
    for path in (_SCHEMA_PATH, _ROUTER_PATH):
        if not path.is_file():
            print(f"::error::대상 파일이 없습니다: {path.relative_to(_REPO_ROOT)} — fail-closed 종료")
            return 1

    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    match = re.search(r"class MarketOhlcIn\(BaseModel\):(.*?)(?=\nclass |\Z)", schema, re.S)
    if match is None:
        print("::error::MarketOhlcIn 을 찾지 못했습니다 — 클래스명이 바뀌었을 수 있습니다 (fail-closed)")
        return 1
    body = match.group(1)

    failures: list[str] = []
    if not re.search(rf"count:\s*int\s*=\s*Field\([^)]*ge={_EXPECTED_MIN}\b", body):
        failures.append(f"count 의 하한이 ge={_EXPECTED_MIN} 이 아닙니다")
    if not re.search(rf"count:\s*int\s*=\s*Field\([^)]*le={_EXPECTED_MAX}\b", body):
        failures.append(f"count 의 상한이 le={_EXPECTED_MAX} 이 아닙니다 — 기간 지정 조회는 GET /bar/daily 입니다")
    for interval in _EXPECTED_INTERVALS:
        if f'"{interval}"' not in body:
            failures.append(f"interval 집합에서 {interval} 이 사라졌습니다")
    for forbidden in ("date_from", "date_to", "start", "end"):
        if re.search(rf"^\s*{forbidden}\s*:", body, re.M):
            failures.append(f"기간 인자({forbidden})가 market_ohlc 에 들어왔습니다 — 두 계약을 섞지 않습니다")

    if 'operation_id="market_ohlc"' not in _ROUTER_PATH.read_text(encoding="utf-8"):
        failures.append("operation_id='market_ohlc' 가 사라졌습니다 — sub-agent 바인딩이 끊깁니다")

    consumers = 0
    for relative in _CONSUMER_PATHS:
        path = _REPO_ROOT / relative
        if not path.is_file():
            failures.append(f"소비자 파일이 없습니다: {relative}")
            continue
        if "market_ohlc" not in path.read_text(encoding="utf-8"):
            failures.append(f"소비자가 더 이상 market_ohlc 를 바인딩하지 않습니다: {relative}")
            continue
        consumers += 1

    if consumers == 0:
        print("::error::market_ohlc 소비자를 0건 수집했습니다 — fail-closed 종료")
        return 1

    print(f"검사한 계약 파일 2개 · 소비자 {consumers}/{len(_CONSUMER_PATHS)}개")
    print(f"계약: count {_EXPECTED_MIN}~{_EXPECTED_MAX}, interval {', '.join(_EXPECTED_INTERVALS)} (최신순)")

    if failures:
        print(f"::error::market_ohlc 계약이 바뀌었습니다 — {len(failures)}건")
        for failure in failures:
            print(f"::error::  {failure}")
        return 1

    print("market_ohlc 계약 유지 — 기간 지정 조회는 backend-service 의 GET /bar/daily 가 맡는다")
    return 0


if __name__ == "__main__":
    sys.exit(test_market_ohlc_contract_unchanged())
