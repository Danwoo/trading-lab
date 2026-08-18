"""맥락 — 「내가 잘한 건가, 그냥 시장이 좋았던 건가」에 답한다 (#204).

## 왜 벤치마크가 복수인가 (스펙 D-Q3)

코스피200 겹치기만으로는 **가장 중요한 질문에 답을 못 한다.**

    내 전략 +18%  ·  코스피200 +9%              →  "이겼다"
    그런데 내 유니버스 동일가중이 +17% 였다면?
      →  종목을 고른 능력이 아니라 그 유니버스가 좋았던 것

**이 모듈은 「내 유니버스 동일가중」을 만든다.** 시장 지수는 B그룹이라 못 한다 —
`MarketDataProvider` 에 지수 메서드가 없고, `DataKind` 에 `index` 가 없고, MCP
`market_index` 는 스칼라 1점이며 코스피200이 없다.

> 동일가중 유니버스는 **적재본에서 계산**하므로 새 소스가 필요 없다. 그래서 키 없이 지금
> 할 수 있고, 지수가 없어도 위 질문의 절반 이상이 답해진다.

## 왜 업종을 사오지 않는가 (스펙 D-Q4)

**팩터 전략은 대부분 의도치 않은 섹터 베팅으로 판명난다.** 저PBR 전략이 실제로는
금융·건설·조선 몰빵인 식이다. 이걸 모르면 자기 전략이 무엇인지 모르는 것이다.

    GICS            국제 표준이지만 유료
    KRX 업종분류     무료지만 국내 전용, 미국과 체계가 다름
    상관 클러스터링   무료 · 데이터가 이미 있음 · 국내·미국 동일 방식

그리고 더 실전적이다 — 같은 업종이어도 안 붙어 다니는 종목이 있고, 다른 업종인데 같이
무너지는 종목이 있다. **트레이더가 알고 싶은 것은 「같이 무너지는 종목끼리 얼마나 들고
있나」지 산업 분류표가 아니다.**

## 이 모듈도 저장소를 모른다

캔들은 호출자가 넘긴다 — `verify_backtest_engine_purity.py` 가 지키는 계산 층이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.backtest.engine import BarSeries

# 상관을 재려면 겹치는 표본이 이만큼은 있어야 한다. 미만이면 **상관을 내지 않는다** —
# 표본 3개짜리 상관계수는 숫자로는 나오지만 아무것도 말하지 않는다(스펙 §8.5.3).
MIN_CORRELATION_SAMPLES = 20

# 이 이상이면 「같이 움직인다」로 본다. 임계값은 스펙에 없어 여기서 정했고, 상수로 빼
# 두어 바꾸기 쉽게 한다 — 화면은 이 값을 근거로 함께 낸다.
CLUSTER_THRESHOLD = 0.7


@dataclass(frozen=True)
class Benchmark:
    """벤치마크 곡선 하나. 이름과 유도 경로가 값과 함께 간다."""

    key: str
    label: str
    dt: list[str]
    equity: list[float]
    derived_from: str

    @property
    def total_return(self) -> float | None:
        if len(self.equity) < 2 or not self.equity[0]:
            return None
        return (self.equity[-1] - self.equity[0]) / self.equity[0]


@dataclass(frozen=True)
class Cluster:
    """같이 움직이는 종목 묶음."""

    instrument_ids: list[int]
    representative: int
    weight_pct: float


@dataclass(frozen=True)
class Concentration:
    """「몇 개 클러스터에 몇 % 집중」."""

    clusters: list[Cluster]
    top_share_pct: float
    derived_from: str
    absent_reason: str | None = None


def equal_weight_universe(series_list: list[BarSeries], initial_cash: float) -> Benchmark:
    """유니버스를 **동일가중**으로 사서 들고 있었다면 어땠나.

    전략이 고른 종목이 아니라 **후보 전체**를 같은 금액씩 사서 가만히 둔 곡선이다.
    이것을 못 이기면 「종목을 고른 능력」이 없었던 것이다.

    종목마다 상장 구간이 달라 날짜가 어긋난다 — **모두가 값을 가진 날만** 쓴다.
    빠진 날을 직전 값으로 메우면 없는 거래일을 만든 것이 된다.
    """
    if not series_list:
        return Benchmark(
            key="equal_weight",
            label="내 유니버스 동일가중",
            dt=[],
            equity=[],
            derived_from="적재된 캔들 — 종목이 없습니다",
        )

    common = set(series_list[0].dt)
    for s in series_list[1:]:
        common &= set(s.dt)
    dates = sorted(common)
    if not dates:
        return Benchmark(
            key="equal_weight",
            label="내 유니버스 동일가중",
            dt=[],
            equity=[],
            derived_from=f"{len(series_list)}종목 — 모두가 값을 가진 날이 없습니다",
        )

    per_symbol = initial_cash / len(series_list)
    index = [{d: i for i, d in enumerate(s.dt)} for s in series_list]
    first_prices = [s.close[index[k][dates[0]]] for k, s in enumerate(series_list)]
    qty = [per_symbol / p if p > 0 else 0.0 for p in first_prices]

    equity = [sum(qty[k] * s.close[index[k][d]] for k, s in enumerate(series_list)) for d in dates]

    return Benchmark(
        key="equal_weight",
        label="내 유니버스 동일가중",
        dt=dates,
        equity=equity,
        derived_from=(f"{len(series_list)}종목을 첫날 동일 금액으로 사서 보유 (공통 거래일 {len(dates)}일)"),
    )


def _returns(series: BarSeries, dates: list[str]) -> list[float]:
    pos = {d: i for i, d in enumerate(series.dt)}
    closes = [series.close[pos[d]] for d in dates]
    return [(closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] else 0.0 for i in range(1, len(closes))]


def correlation(a: list[float], b: list[float]) -> float | None:
    """피어슨 상관. 표본이 모자라거나 한쪽이 안 움직이면 **None** 이다 — 0 이 아니다."""
    n = min(len(a), len(b))
    if n < MIN_CORRELATION_SAMPLES:
        return None
    a, b = a[:n], b[:n]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0 or var_b <= 0:
        return None
    return cov / (var_a * var_b) ** 0.5


def cluster_concentration(series_list: list[BarSeries], weights: dict[int, float] | None = None) -> Concentration:
    """보유 종목이 **몇 개 클러스터에 몇 % 집중**됐나.

    업종표를 사오지 않고 **상관으로 묶는다** — 같이 무너지는 종목끼리 얼마나 들고 있는지가
    질문이지 산업 분류가 아니다.

    묶는 방법은 단순 연결(single-linkage)이다: 임계 이상으로 붙은 것끼리 한 덩어리.
    """
    if len(series_list) < 2:
        return Concentration(
            clusters=[],
            top_share_pct=0.0,
            derived_from="보유 종목의 일별 수익률 상관",
            absent_reason="종목이 2개 미만이라 묶을 것이 없습니다",
        )

    common = set(series_list[0].dt)
    for s in series_list[1:]:
        common &= set(s.dt)
    dates = sorted(common)
    if len(dates) - 1 < MIN_CORRELATION_SAMPLES:
        return Concentration(
            clusters=[],
            top_share_pct=0.0,
            derived_from="보유 종목의 일별 수익률 상관",
            absent_reason=(
                f"공통 거래일이 {max(len(dates) - 1, 0)}일이라 상관을 내지 않습니다 "
                f"({MIN_CORRELATION_SAMPLES}일 미만은 숫자만 나오고 뜻이 없습니다)"
            ),
        )

    rets = [_returns(s, dates) for s in series_list]
    n = len(series_list)

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs_measured = 0
    for i in range(n):
        for j in range(i + 1, n):
            corr = correlation(rets[i], rets[j])
            if corr is None:
                continue
            pairs_measured += 1
            if corr >= CLUSTER_THRESHOLD:
                parent[find(i)] = find(j)

    if pairs_measured == 0:
        return Concentration(
            clusters=[],
            top_share_pct=0.0,
            derived_from="보유 종목의 일별 수익률 상관",
            absent_reason="상관을 낼 수 있는 종목 쌍이 없습니다 (가격이 움직이지 않았습니다)",
        )

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    total_weight = sum((weights or {}).values()) or float(n)
    clusters: list[Cluster] = []
    for members in groups.values():
        ids = [series_list[i].instrument_id for i in members]
        weight = sum((weights or {}).get(iid, 1.0) for iid in ids)
        clusters.append(
            Cluster(
                instrument_ids=sorted(ids),
                representative=min(ids),
                weight_pct=weight / total_weight * 100,
            )
        )
    clusters.sort(key=lambda c: c.weight_pct, reverse=True)

    # 「3개 클러스터에 82% 집중」 — 상위 몇 개가 얼마를 차지하나.
    top = clusters[: min(3, len(clusters))]
    return Concentration(
        clusters=clusters,
        top_share_pct=sum(c.weight_pct for c in top),
        derived_from=(
            f"{n}종목의 일별 수익률 상관 {pairs_measured}쌍 · "
            f"상관 {CLUSTER_THRESHOLD} 이상을 같은 덩어리로 (공통 거래일 {len(dates)}일)"
        ),
    )
