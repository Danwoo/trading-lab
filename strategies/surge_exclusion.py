"""급등 제외 필터 — 이미 크게 오른 종목을 후보에서 뺀다.

혼자 쓰는 전략이 아니라 다른 전략과 AND 로 묶어 쓰는 필터다.
"""

STRATEGY = {
    "key": "surge_exclusion",
    "name": "급등 제외 필터",
    "summary": "최근 일정 기간에 기준 이상 오른 종목은 사지 않는다",
    "timeframe": "1d",
    "params": [
        {
            "name": "lookback_days",
            "label": "돌아보는 기간",
            "type": "int",
            "default": 5,
            "min": 2,
            "max": 60,
            "step": 1,
            "unit": "일",
        },
        {
            "name": "surge_pct",
            "label": "급등 기준",
            "type": "percent",
            "default": 20.0,
            "min": 3.0,
            "max": 100.0,
            "step": 1.0,
            "help": "돌아보는 기간에 이만큼 넘게 오른 종목을 급등으로 본다.",
        },
        {
            "name": "measure",
            "label": "무엇으로 재나",
            "type": "choice",
            "default": "close",
            "choices": [
                {"value": "close", "label": "종가 기준"},
                {"value": "high", "label": "기간 중 고가 기준"},
            ],
            "help": "고가 기준은 장중에 찔렀다 내려온 것도 급등으로 본다.",
        },
    ],
}


def indicators(bars, params):
    """돌아보는 기간의 상승률을 계산한다."""
    lookback = params["lookback_days"]
    measure = params["measure"]
    rise_pct: list[float | None] = []

    for index, bar in enumerate(bars):
        if index < lookback:
            rise_pct.append(None)
            continue
        base = bars[index - lookback]["close"]
        if base <= 0:
            rise_pct.append(None)
            continue
        window = bars[index - lookback + 1 : index + 1]
        peak = max(candle["high"] for candle in window) if measure == "high" else bar["close"]
        rise_pct.append((peak - base) / base * 100)

    return {"rise_pct": rise_pct}


def entry(ctx):
    """급등하지 않았을 때만 통과시킨다."""
    rise = ctx["indicators"]["rise_pct"][ctx["index"]]
    if rise is None:
        return False
    return rise < ctx["params"]["surge_pct"]


def exit(ctx):
    """필터라서 청산 신호를 내지 않는다."""
    return False
