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


#: 라이브러리가 **세션 경계를 틀리게 아는** 날 (캘린더 코드 → 날짜들).
#:
#: 한국의 대학수학능력시험일은 KRX 개장이 1시간 늦고(10:00) 폐장도 1시간 늦다(16:30).
#: `exchange_calendars` 4.13.2 의 `precomputed_csat_days` 는 **2020-12-03 에서 끊긴다** —
#: 그 뒤 수능일을 물으면 평일과 같은 09:00 을 답한다. 실측:
#:
#:     2019-11-14 (수능) → KST 10:00   안다
#:     2020-12-03 (수능) → KST 10:00   안다
#:     2021-11-18 (수능) → KST 09:00   틀렸다
#:     2023-11-16 (수능) → KST 09:00   틀렸다
#:     2025-11-13 (수능) → KST 09:00   틀렸다
#:
#: **이 목록은 「접지 마라」는 표시이지 보정값이 아니다.** 우리가 아는 것은 「캘린더가 틀렸다」
#: 까지이고, 그 날의 정확한 경계를 여기 적어 접으면 그 값이 또 하나의 주장이 된다. 못 믿는
#: 날은 소스 일봉을 그대로 답하고 `session_scope` 를 `unknown` 으로 둔다 (#255 리드 결정 A′).
#:
#: 원본은 한국교육과정평가원의 수능 시행일 공고이고, `scripts/verify_calendar_corrections.py`
#: 가 라이브러리가 나중에 고쳤는지 매번 되묻는다.
UNRELIABLE_SESSION_BOUNDS: dict[str, frozenset[dt.date]] = {
    "XKRX": frozenset(
        {
            dt.date(2021, 11, 18),  # 2022학년도 수능 — 개장 10:00 (라이브러리는 09:00)
            dt.date(2022, 11, 17),  # 2023학년도 수능
            dt.date(2023, 11, 16),  # 2024학년도 수능
            dt.date(2024, 11, 14),  # 2025학년도 수능
            dt.date(2025, 11, 13),  # 2026학년도 수능
        }
    ),
}


#: 라이브러리가 **거래일이라고 보지만 실제로는 휴장**인 날 (캘린더 코드 → 날짜들).
#:
#: `exchange_calendars` 는 한국의 그해 결정 사항을 늦게 반영한다. 그 차이는 조용하지 않다 —
#: 갭 검출이 「영원히 못 채우는 결측」을 매번 보고하고, 백테스트가 장이 안 선 날에 신호를
#: 판정한다. 실측으로 잡은 것만 적는다 (2026-08-19, 토스 실적재 3종목이 **같은 이틀**을
#: 빠뜨렸다 — 종목 결손이 아니라 휴장의 서명이다).
#:
#: **원본은 KRX 휴장일 공지이고, 갱신은 연 1회(전년 12월) + 실데이터가 말할 때다** —
#: 절차와 근거는 `.docs/4-아키텍처/시세적재-구현설계.md` §1.3.1 이 정본이다.
#:
#: **여기 적은 날은 `scripts/verify_calendar_corrections.py` 가 매번 되묻는다** — 라이브러리가
#: 나중에 고치면 이 보정이 거짓이 되므로, 그때 실패해서 지우라고 말한다.
EXTRA_CLOSURES: dict[str, frozenset[dt.date]] = {
    "XKRX": frozenset(
        {
            # 각 줄은 **KRX 휴장일 공지**(한국거래소 「휴장일 안내」)가 정본이고, 옆의 사유가
            # 그 공지에서 온 근거다. 실적재 관측은 **발견의 계기**이지 근거가 아니다 —
            # 「이 날 데이터가 없다」는 소스 장애·수집 실패로도 같은 서명을 낸다.
            dt.date(2026, 6, 3),  # 제9회 전국동시지방선거일 — 공직선거법상 임시공휴일 (KRX 휴장)
            dt.date(2026, 7, 17),  # 제헌절 — 2026년부터 공휴일 재지정 (KRX 휴장)
        }
    ),
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
    closed = extra_closures(market)
    return [ts.date() for ts in calendar.sessions_in_range(date_from, date_to) if ts.date() not in closed]


def extra_closures(market: str) -> frozenset[dt.date]:
    """이 시장에 더 뺄 휴장일. **키는 `calendar_code` 가 정본**이다 —
    `exchange_calendars` 의 `.name` 표기에 기대면 표기가 바뀔 때 보정이 **조용히 무효**가 된다."""
    return EXTRA_CLOSURES.get(calendar_code(market), frozenset())


def is_session(market: str, day: dt.date) -> bool:
    """그 날짜가 이 시장의 거래일인가. 보정 목록(`EXTRA_CLOSURES`)을 빼고 답한다."""
    if day in extra_closures(market):
        return False
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
        return _skip_closures(market, calendar.last_session.date())
    previous = calendar.previous_close(asof_utc)
    if previous is None:
        return None
    return _skip_closures(market, calendar.minute_to_session(previous, direction="previous").date())


def unreliable_bounds(market: str) -> frozenset[dt.date]:
    """이 시장에서 **세션 경계를 못 믿는** 날."""
    return UNRELIABLE_SESSION_BOUNDS.get(calendar_code(market), frozenset())


def session_bounds(market: str, day: dt.date) -> tuple[dt.datetime, dt.datetime] | None:
    """그 날 정규장의 시작·끝을 **시장 현지 naive** 로 준다. 못 믿으면 `None`.

    `None` 을 주는 경우는 셋이다 — 거래일이 아니거나, 캘린더 범위 밖이거나, 경계를 못 믿는 날
    (`UNRELIABLE_SESSION_BOUNDS`)이다. 부르는 쪽은 `None` 을 「접지 마라」로 읽는다.
    """
    if day in unreliable_bounds(market) or day in extra_closures(market):
        return None
    calendar = get_market_calendar(market)
    if not (calendar.first_session.date() <= day <= calendar.last_session.date()):
        return None
    if not calendar.is_session(day):
        return None

    # `session_open` 은 pandas Timestamp 를 준다 — DB 파라미터·비교에 그대로 실으면 드라이버마다
    # 다르게 다뤄진다. 표준 `datetime` 으로 내려 계약을 하나로 둔다.
    def _plain(value) -> dt.datetime:
        naive = market_local_naive(market, value)
        return dt.datetime(naive.year, naive.month, naive.day, naive.hour, naive.minute, naive.second)

    return (_plain(calendar.session_open(day)), _plain(calendar.session_close(day)))


def _skip_closures(market: str, day: dt.date | None) -> dt.date | None:
    """보정으로 뺀 날에 걸리면 그 **앞의 거래일**로 물러난다.

    이 함수가 보정 밖에 있으면 2026-07-18 에 「마지막 완료 거래일 = 2026-07-17」이 나오고,
    MD-AD-22 가 그 날을 재요청 기준으로 삼는다 — 이 보정층이 막으려던 바로 그 오류가
    다른 문으로 들어온다.
    """
    closed = extra_closures(market)
    if not closed or day is None:
        return day
    calendar = get_market_calendar(market)
    first = calendar.first_session.date()
    while day in closed and day > first:
        previous = calendar.previous_session(day)
        if previous is None:
            return None
        day = previous.date()
    return day
