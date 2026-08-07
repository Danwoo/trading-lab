"""응답 내 중복 타임스탬프 병합 (MD-AD-24) — 어댑터가 정규화 모델을 내보내기 **직전**에 부른다.

upsert(MD-AD-16)는 **배치 간** 중복(같은 구간을 다시 적재)만 해결한다. 한 응답 안에 같은
타임스탬프가 두 번 들어오는 경우는 upsert 로도 걸러지지 않고 마지막 행이 이긴다 — 어느 행이
이길지가 응답 순서에 달린 조용한 비결정이다. freqtrade `clean_ohlcv_dataframe` 의 규칙을 그대로
채택해 여기서 결정론적으로 접는다.

| 필드 | 규칙 |
|---|---|
| open | first |
| high | max |
| low | min |
| close | last |
| volume | **max** (합계 아님 — 별개 거래의 합산이 아니라 같은 스냅샷의 중복 발신으로 본다) |

병합은 행 소실이 아니므로 `tn_ingest_run.skipped_rows` 에 넣지 않는다 — 정상적인 응답 패턴이라
적재 이력에 노이즈를 만들 필요가 없다. 건수는 로그에만 남긴다(구현설계 §4.4).

소스 사정을 모르는 순수 함수라 특정 `providers/<소스>/` 밑이 아니라 이 층에 둔다 — 소스마다
복붙하면 규칙이 갈라진다.
"""

from core.logger import logger

from providers.models import NormalizedBar


def merge_duplicate_bars(bars: list[NormalizedBar], *, source: str) -> list[NormalizedBar]:
    """`(market, symbol, ts)` 가 같은 캔들을 하나로 접는다. 입력 순서를 first/last 의 기준으로
    삼으므로 어댑터는 소스가 준 순서를 흐트러뜨리기 전에 이 함수를 부른다."""
    merged: dict[tuple[str, str, object], NormalizedBar] = {}
    duplicates = 0

    for bar in bars:
        key = (bar.market, bar.symbol, bar.ts)
        previous = merged.get(key)
        if previous is None:
            merged[key] = bar
            continue
        duplicates += 1
        merged[key] = previous.model_copy(
            update={
                "high": max(previous.high, bar.high),
                "low": min(previous.low, bar.low),
                "close": bar.close,
                "volume": max(previous.volume, bar.volume),
                "trade_value": _max_optional(previous.trade_value, bar.trade_value),
            }
        )

    if duplicates:
        logger.info(f"[{source}] 응답 내 중복 캔들 {duplicates}건 병합 (MD-AD-24)")
    return list(merged.values())


def _max_optional(left, right):
    """거래대금은 선택 필드다 — 한쪽만 있으면 있는 쪽, 둘 다 있으면 큰 쪽(volume 과 같은 근거)."""
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
