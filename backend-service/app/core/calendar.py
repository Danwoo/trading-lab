"""거래일 캘린더 — `market` 문자열이 `exchange_calendars` 를 만나는 유일한 지점 (MD-AD-21).

이 진입점이 하나여야 하는 이유: 매핑을 provider 어댑터마다 두면 소스가 늘 때 갈라지고, 갈라진
뒤에는 "이 종목의 거래일"이 소스마다 달라진다. 갭 검출(MD-AD-23)과 미완성 캔들 재수집
(MD-AD-22)이 둘 다 이 매핑 위에 서 있어, 어긋나면 결측과 휴장을 구분하지 못한다.

`XNAS` 에 대한 메모 — 구현설계 §1.3 은 "`exchange_calendars` 에 `XNAS` 가 없다"를 근거로 미국
세 시장을 `XNYS` 하나로 고정했다. 설치본(4.13.2)에는 `XNAS` 가 실재하고 2026년 세션 목록이
`XNYS` 와 251일 전부 일치한다 — 근거는 낡았지만 **결정 자체는 유효**하므로 매핑은 설계대로
둔다(설계가 정본, 관측은 PR 본문 「발견」에 남긴다).
"""

from __future__ import annotations

import datetime as dt
from functools import cache

import exchange_calendars as xcals
from core.exceptions import BadRequestError

# market → 캘린더 코드. 구현설계 §1.3 표를 그대로 옮긴 것이며, 이 dict 가 유일한 정의다.
CALENDAR_CODE_BY_MARKET: dict[str, str] = {
    "KOSPI": "XKRX",
    "KOSDAQ": "XKRX",
    "KONEX": "XKRX",
    "NASDAQ": "XNYS",
    "NYSE": "XNYS",
    "AMEX": "XNYS",
}


def calendar_code(market: str) -> str:
    """`market` 의 캘린더 코드. 모르는 시장은 조용히 기본값으로 떨어지지 않고 거절한다 —
    오타 하나가 "휴장일이 하나도 없는 시장"으로 둔갑해 갭 검출을 통째로 망가뜨린다."""
    code = CALENDAR_CODE_BY_MARKET.get(market.upper())
    if code is None:
        known = ", ".join(sorted(CALENDAR_CODE_BY_MARKET))
        raise BadRequestError(f"거래일 캘린더를 모르는 시장입니다: {market!r} (아는 시장: {known})")
    return code


@cache
def get_market_calendar(market: str) -> xcals.ExchangeCalendar:
    """`market` 의 거래일 캘린더. `exchange_calendars` 를 감싸는 유일한 진입점이다."""
    return xcals.get_calendar(calendar_code(market))


def sessions_between(market: str, date_from: dt.date, date_to: dt.date) -> list[dt.date]:
    """[date_from, date_to] 의 거래일 목록(양 끝 포함). 캘린더 수록 범위 밖은 빈 목록이 아니라
    거절이다 — 범위 밖을 0건으로 돌려주면 "그 구간엔 거래일이 없다"와 구분되지 않는다."""
    calendar = get_market_calendar(market)
    first, last = calendar.first_session.date(), calendar.last_session.date()
    if date_from < first or date_to > last:
        raise BadRequestError(
            f"캘린더 수록 범위를 벗어난 기간입니다: {date_from}~{date_to} ({calendar.name} 수록 범위 {first}~{last})"
        )
    return [ts.date() for ts in calendar.sessions_in_range(date_from, date_to)]


def is_session(market: str, day: dt.date) -> bool:
    """그 날짜가 이 시장의 거래일인가."""
    return get_market_calendar(market).is_session(day)


def market_local_naive(market: str, when: dt.datetime) -> dt.datetime:
    """UTC 시각을 그 시장의 **현지 벽시계 시각**(tz 없는 naive)으로 바꾼다.

    분봉의 시간축은 사용자 타임존이 아니라 **시장 시각 고정**이다(2026-07-30 결정). 저장 시각을
    UTC 로 두면 화면이 어디서 열리든 09:30 개장 캔들이 09:30 으로 보이지 않는다 — 표시 계층에서
    되돌리려면 시장 tz 를 프론트까지 들고 가야 하고, 그 순간 공용 `formatDate` 의 사용자 타임존
    기본값과 섞인다. 그래서 **저장 시점에** 시장 벽시계로 고정한다.

    정규장 시간대에는 DST 전환이 일어나지 않으므로(전환은 일요일 새벽) 같은 벽시계 시각이 하루에
    두 번 나오는 모호성은 생기지 않는다.
    """
    tz = get_market_calendar(market).tz
    aware = when if when.tzinfo else when.replace(tzinfo=dt.UTC)
    return aware.astimezone(tz).replace(tzinfo=None)


def last_completed_session(market: str, asof: dt.datetime) -> dt.date | None:
    """`asof` 시점 기준으로 **이미 끝난** 마지막 거래일.

    MD-AD-22 가 "마지막 저장 거래일을 항상 재요청한다"고 정한 판단의 근거가 이 함수다 —
    장중이면 오늘은 아직 완료된 거래일이 아니므로 어제(직전 거래일)가 답이다. 시장 시각 기준으로
    판정한다(캘린더의 세션 종료 시각은 tz-aware UTC 다).
    """
    calendar = get_market_calendar(market)
    asof_utc = asof.astimezone(dt.UTC) if asof.tzinfo else asof.replace(tzinfo=dt.UTC)
    if asof_utc.date() > calendar.last_session.date():
        return calendar.last_session.date()
    previous = calendar.previous_close(asof_utc)
    if previous is None:
        return None
    return calendar.minute_to_session(previous, direction="previous").date()
