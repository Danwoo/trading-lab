"""주문 계열 호출의 코드 레벨 차단 — 운영 규약 C절 (2026-08-19).

`TRADING_LIVE_ENABLED` 가 **문자열 "true" 와 정확히 일치**할 때만 주문 경로가 열린다.
기본은 닫힘이고, 이 기본값을 바꾸는 변경은 리드 승인 사항이다.

Settings 를 거치지 않고 환경변수를 직접 읽는 이유 — 이 가드는 설정 배관(어느 config 가
주입됐는가)에 **의존하면 안 되는** 마지막 방어층이다. 배관이 바뀌거나 테스트가 가짜 설정을
꽂아도 가드는 실제 프로세스 환경만 본다.
"""

from __future__ import annotations

import os

#: 주문 계열 경로 접두 — 공식 사양의 주문·조건주문 (README.md api-reference).
ORDER_PATH_PREFIXES = ("/api/v1/orders", "/api/v1/conditional-orders")

#: 계좌 계열 — C절: 잔고·보유종목 조회는 리드가 그 세션에서 명시 요청했을 때만.
ACCOUNT_PATH_PREFIXES = ("/api/v1/accounts",)


class TradingLiveDisabled(Exception):
    """주문 호출이 코드 레벨에서 막혔다. 값·토큰을 담지 않는다."""


class AccountReadBlocked(Exception):
    """계좌 조회가 기본 차단됐다 — 호출부가 명시 플래그를 줘야 열린다."""


def _normalized(path: str) -> str:
    """dot-segment 를 접은 경로. **판정 전에** 접는다 — httpx 가 전송 직전에 접으므로,
    접기 전 문자열로 판정하면 `/api/v1/candles/../orders` 가 가드를 지나 주문으로 나간다.
    """
    parts: list[str] = []
    for segment in path.split("?", 1)[0].split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/" + "/".join(parts)


def assert_path_allowed(path: str, *, allow_account_read: bool = False) -> None:
    """모든 토스 API 호출이 지나는 관문. 주문은 플래그, 계좌는 호출부 명시가 있어야 통과한다."""
    path = _normalized(path)
    if path.startswith(ORDER_PATH_PREFIXES):
        if os.environ.get("TRADING_LIVE_ENABLED") != "true":
            raise TradingLiveDisabled(
                "주문 API 는 코드 레벨에서 차단돼 있습니다 — TRADING_LIVE_ENABLED=true 를 명시해야 열립니다 (기본 닫힘, 기본값 변경은 승인 사항)"
            )
    if path.startswith(ACCOUNT_PATH_PREFIXES) and not allow_account_read:
        raise AccountReadBlocked(
            "계좌 조회는 기본 차단입니다 — 리드가 명시 요청한 경로에서만 allow_account_read 로 엽니다"
        )
