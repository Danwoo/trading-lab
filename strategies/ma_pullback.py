"""이동평균 눌림목 — 평균선 아래로 눌렸다가 돌아서는 자리를 잡는다."""

STRATEGY = {
    "key": "ma_pullback",
    "name": "이동평균 눌림목",
    "summary": "평균선 아래로 눌린 종목이 다시 평균선을 되찾을 때 산다",
    "timeframe": "1d",
    "params": [
        {
            "name": "ma_period",
            "label": "평균선 기간",
            "type": "int",
            "default": 20,
            "min": 5,
            "max": 120,
            "step": 1,
            "unit": "일",
            "help": "길수록 큰 흐름만 본다.",
        },
        {
            "name": "pullback_pct",
            "label": "눌림 깊이",
            "type": "percent",
            "default": 3.0,
            "min": 0.5,
            "max": 15.0,
            "step": 0.5,
            "help": "평균선 대비 이만큼 아래로 내려온 것을 눌림으로 본다.",
        },
        {
            "name": "recover_confirm",
            "label": "회복 확인",
            "type": "bool",
            "default": True,
            "help": "평균선을 되찾은 봉이 나온 뒤에 산다. 끄면 눌린 자리에서 바로 산다.",
        },
    ],
}


def indicators(bars, params):
    """평균선과 평균선 대비 이격을 계산한다.

    `bars` 는 오래된 것부터 정렬된 캔들 목록이고, 각 캔들은 `close` 를 갖는다.
    """
    period = params["ma_period"]
    closes = [bar["close"] for bar in bars]
    moving_average: list[float | None] = []
    gap_pct: list[float | None] = []

    for index, close in enumerate(closes):
        if index + 1 < period:
            moving_average.append(None)
            gap_pct.append(None)
            continue
        window = closes[index + 1 - period : index + 1]
        average = sum(window) / period
        moving_average.append(average)
        gap_pct.append((close - average) / average * 100)

    return {"moving_average": moving_average, "gap_pct": gap_pct}


def entry(ctx):
    """평균선 아래로 눌렸다가 되찾으면 산다."""
    gaps = ctx["indicators"]["gap_pct"]
    index = ctx["index"]
    if index < 1 or gaps[index] is None or gaps[index - 1] is None:
        return False

    pulled_back = gaps[index - 1] <= -ctx["params"]["pullback_pct"]
    if not pulled_back:
        return False
    if not ctx["params"]["recover_confirm"]:
        return True
    return gaps[index] >= 0


def exit(ctx):
    """평균선 아래로 다시 내려가면 판다."""
    gaps = ctx["indicators"]["gap_pct"]
    gap = gaps[ctx["index"]]
    return gap is not None and gap < 0
