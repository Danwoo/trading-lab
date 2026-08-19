"""샘플 캔들 생성 — **키 없이 백테스트를 한 번은 끝까지 돌려보게 한다** (#217).

## 왜 파일이 아니라 생성인가

CSV 를 레포에 넣으면 몇 MB 가 커밋에 남고, 구간을 넓히려면 파일을 다시 만들어야 한다.
**같은 씨앗에서 같은 값이 나오는 생성기**면 파일 없이 어떤 구간이든 낼 수 있고, 커밋에
바이너리가 안 들어간다(공개 배포 트리 게이트의 자산 등록 대상도 아니다).

## 재현 가능해야 한다

`random` 모듈을 쓰지 않는다 — 프로세스마다 달라지면 「어제 본 곡선」을 오늘 못 본다.
종목·날짜에서 **결정론적으로** 값을 만든다: 같은 입력이면 언제 어디서 돌려도 같은 캔들이다.

## 실데이터인 척하지 않는다

값은 합성이고 티커도 샘플이다(`SAMPLE1`…). 이것이 실제 시세로 오인되면 「없는 계산을 한
척하는 값」과 같은 부류가 된다 — 그래서 소스 이름이 `sample` 이고, 캐패빌리티 사유에
그 사실을 적으며, 종목명에도 「샘플」이 들어간다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math

# 샘플 종목 — 시장마다 소수. 실재 티커와 겹치지 않게 접두사를 붙인다.
SAMPLE_INSTRUMENTS: dict[str, list[tuple[str, str]]] = {
    "KR": [("SAMPLE001", "샘플 대형주"), ("SAMPLE002", "샘플 중형주"), ("SAMPLE003", "샘플 변동주")],
    "US": [("SAMPLEA", "Sample Large Cap"), ("SAMPLEB", "Sample Mid Cap")],
}

# 종목마다 다른 성격을 준다 — 하나만 있으면 격자가 늘 같은 답을 낸다.
#   base   시작가
#   drift  하루 평균 추세 (연 기준으로 완만하게)
#   swing  주기 진폭 (%)
#   noise  결정론적 흔들림 폭 (%)
_PROFILE: dict[str, tuple[float, float, float, float]] = {
    "SAMPLE001": (70_000.0, 0.00025, 6.0, 1.2),
    "SAMPLE002": (35_000.0, 0.00010, 9.0, 2.0),
    "SAMPLE003": (12_000.0, -0.00005, 14.0, 3.5),
    "SAMPLEA": (180.0, 0.00030, 5.0, 1.0),
    "SAMPLEB": (60.0, 0.00008, 11.0, 2.4),
}


def is_trading_day(day: dt.date) -> bool:
    """주말만 뺀다 — 공휴일 달력은 시장마다 다르고, 샘플에 그 정확도는 필요 없다.

    **이 단순화를 숨기지 않는다**: 캐패빌리티 사유가 「샘플」임을 밝히고, 화면도 그렇게 읽는다.
    """
    return day.weekday() < 5


def _wobble(symbol: str, day: dt.date) -> float:
    """종목·날짜에서 결정론적으로 뽑은 −1.0 ~ 1.0.

    해시를 쓰는 이유는 난수처럼 보이되 **재현되기** 때문이다. 같은 입력이면 어느 기계에서도
    같은 값이라, 어제 본 곡선을 오늘 다시 본다.
    """
    digest = hashlib.sha256(f"{symbol}:{day.isoformat()}".encode()).digest()
    raw = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return raw * 2 - 1


def close_price(symbol: str, day: dt.date) -> float:
    """그날의 종가."""
    base, drift, swing_pct, noise_pct = _PROFILE.get(symbol, (100.0, 0.0, 8.0, 2.0))
    n = (day - dt.date(2020, 1, 1)).days
    trend = base * (1 + drift) ** n
    swing = trend * (swing_pct / 100) * math.sin(n / 21.0)  # 약 한 달 주기
    noise = trend * (noise_pct / 100) * _wobble(symbol, day)
    return round(max(trend + swing + noise, 0.01), 2)


def daily_bars(symbol: str, date_from: dt.date, date_to: dt.date) -> list[dict]:
    """구간의 일봉. 거래일만 낸다.

    시가·고가·저가는 종가에서 파생한다 — 샘플이므로 정교할 필요는 없지만 **불변식은 지킨다**:
    `low <= open,close <= high`. 이것이 깨지면 캔들 차트가 뒤집힌 봉을 그린다.
    """
    out: list[dict] = []
    day = date_from
    while day <= date_to:
        if is_trading_day(day):
            close = close_price(symbol, day)
            prev = close_price(symbol, day - dt.timedelta(days=1))
            open_ = round((prev + close) / 2, 2)
            spread = abs(close - open_) + close * 0.004
            out.append(
                {
                    "dt": day,
                    "open": open_,
                    "high": round(max(open_, close) + spread * 0.5, 2),
                    "low": round(max(min(open_, close) - spread * 0.5, 0.01), 2),
                    "close": close,
                    "volume": 100_000 + int(abs(_wobble(symbol, day)) * 900_000),
                }
            )
        day += dt.timedelta(days=1)
    return out
