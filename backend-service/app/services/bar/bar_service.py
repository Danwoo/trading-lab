"""캔들 조회 서비스 (갈래 1). **provider 를 주입받지 않는다** — MD-AD-19 를 배선으로 강제한다.

주입받는 것은 `BarRepository`(적재본)와 `CapabilityService`(왜 비었는지)뿐이다. 차트가 소스를
직접 부를 수 있는 통로가 생성자에 존재하지 않는 것이 이 파일의 요점이며, `core/container.py`
의 이 서비스 배선에 provider 가 없다는 사실이 그 증거다.

"없는 데이터는 정직하게 비운다"(FR-021)를 갈래로 나눠 답한다:

| 상황 | 응답 |
|---|---|
| 적재본에 행이 있다 | 200 + 캔들 (**capability 와 무관하다** — 아래 참조) |
| 종목이 마스터에 없다 | 404 (오타·미상장은 사용자가 고칠 문제다) |
| 행이 없고, 이 시장의 캔들을 줄 소스도 없다 | 200 + 빈 배열 + 소스별 사유 |
| 행이 없고, 소스는 있다 | 200 + 빈 배열 + "아직 적재되지 않았습니다" |

**행이 있으면 capability 를 묻지 않는 이유**(실측으로 잡은 순서 결함): capability 는 "지금 새로
받아올 수 있나"이고 적재본은 "예전에 받아 둔 것"이다. 둘을 같은 게이트로 묶으면, 키가 만료되거나
소스 계약이 끝난 순간 **이미 쌓아 둔 10년치 캔들이 화면에서 사라진다.** 갈래 1(적재본 읽기)이
provider 를 모른다는 MD-AD-19 는 이 순서까지 포함한 말이다.
"""

import datetime as dt

from core.calendar import market_local_naive, session_bounds, sessions_between
from core.exceptions import BadRequestError, NotFoundError
from providers.base import CREDENTIAL_MISSING_CODE, NOT_CANONICAL_CODE
from repositories.bar.bar_repository import BarRepository
from services.capability.capability_service import CapabilityService

# 한 응답에 실을 수 있는 캔들 수 상한. 일봉 10년(약 2,500)과 하루치 1분봉(390×?)을 모두 담되,
# 브라우저가 한 번에 그리지 못할 양은 거절한다.
MAX_BARS = 5000

# 합성 가능한 분봉 주기 (MD-AD-26 — 저장은 1분봉만, 나머지는 여기서 만든다).
SYNTHESIZABLE_INTERVALS = (1, 5, 15, 30, 60)


class BarService:
    #: 접기용 분봉 조회 상한. 일봉 상한(`MAX_BARS`)만큼의 날을 접으려면 하루 390분 × 그 수인데,
    #: 그것을 한 번에 읽으면 조회가 무거워진다. **모자라면 뒷날이 안 접히고 `mixed` 로 답한다** —
    #: 조용히 틀린 값을 주는 것보다 「일부만 접었다」를 정직히 말하는 쪽이다.
    MINUTE_FOLD_LIMIT = 200_000

    def __init__(self, bar_repository: BarRepository, capability_service: CapabilityService):
        self.bar_repository = bar_repository
        self.capability_service = capability_service

    def _unavailable(self, workspace_id: int | None, market: str, data_kind: str) -> tuple[str | None, str | None]:
        """이 시장·데이터종류를 줄 수 있는 소스가 하나라도 있으면 `(None, None)`, 없으면 `(사유, 코드)`.

        코드는 **막은 이유가 전부 「키가 아직 없다」일 때만** `credential_missing` 이다. 하나라도
        다른 사유(제공 범위 밖·장애)가 섞이면 코드를 안 준다 — 화면이 그 경우를 임시 데이터로
        덮으면 진짜 결손이 조용히 숨는다.
        """
        rows = [
            row
            for row in self.capability_service.list_capabilities(workspace_id, market)
            if row["data_kind"] == data_kind
        ]
        if not rows:
            return f"{market} 시장의 {data_kind} 를 다루는 소스가 등록되어 있지 않습니다", None
        if any(row["available"] for row in rows):
            return None, None
        reason = " / ".join(f"{row['source']}: {row['reason']}" for row in rows if row["reason"])
        # 「정본이 아니다」는 막은 이유가 아니다 — 그 시장의 정본이 따로 있다는 안내이므로
        # 결손 집계에서 뺀다. 넣고 세면 소스를 하나 붙일 때마다 코드가 사라진다.
        codes = {row.get("code") for row in rows if row.get("code") != NOT_CANONICAL_CODE}
        return reason, CREDENTIAL_MISSING_CODE if codes == {CREDENTIAL_MISSING_CODE} else None

    def _missing_instrument_error(self, market: str, symbol: str) -> NotFoundError:
        """「없는 종목」과 「아직 안 받은 종목」을 가른다.

        그 시장의 마스터가 통째로 비어 있으면 **둘 중 무엇인지 알 수 없다** — 그때 「없는
        종목입니다」라고 답하면 사용자가 멀쩡한 종목 코드를 의심하고 다음에 무엇을 할지도
        잃는다. 소스가 가용한데 아직 안 돌린 상태는 키 없이 도는 소스가 생기면서 처음 생겼다.
        """
        if self.bar_repository.has_any_instrument(market):
            return NotFoundError(f"종목 마스터에 없는 종목입니다: {market} {symbol}")
        return NotFoundError(
            f"{market} 종목 마스터를 아직 한 번도 받지 않았습니다 — {symbol} 이 없는 종목인지"
            f" 아직 안 받은 것인지 알 수 없습니다. 「적재」에서 종목 마스터를 먼저 받아 오세요."
        )

    def _instrument(self, market: str, symbol: str) -> dict:
        instrument = self.bar_repository.select_instrument({"market": market, "symbol": symbol})
        if not instrument:
            raise self._missing_instrument_error(market, symbol)
        return instrument

    @staticmethod
    def _provenance(rows: list[dict]) -> tuple[str | None, str | None, str | None]:
        """적재본이 스스로 밝히는 출처 — 소스·수정주가 정책·기준 시각(FR-019)."""
        if not rows:
            return None, None, None
        sources = sorted({row["source"] for row in rows})
        policies = sorted({row["adj_policy"] for row in rows})
        ingested = max(row["ingested_at"] for row in rows if row.get("ingested_at"))
        return (
            ",".join(sources),
            ",".join(policies),
            ingested.isoformat(timespec="seconds") if ingested else None,
        )

    @staticmethod
    def _session_scope(rows: list[dict]) -> str | None:
        """이 구간의 일봉이 **어느 창**을 덮는가 — `regular`·`unknown`·`mixed`.

        섞이면 `mixed` 다. 한쪽으로 뭉개면 「이 구간은 정규장 값이다」가 절반만 참인 채로
        화면에 나가고, 그 절반이 백테스트 체결가가 된다 (#255).
        """
        scopes = {row.get("session_scope") or "unknown" for row in rows}
        if not scopes:
            return None
        return scopes.pop() if len(scopes) == 1 else "mixed"

    def select_daily_bar_list(self, args: dict) -> dict:
        market, symbol = args["market"].upper(), args["symbol"].upper()
        date_from, date_to = args["date_from"], args["date_to"]
        limit = self._validated_limit(args.get("limit"))
        if date_from > date_to:
            raise BadRequestError("date_from 이 date_to 보다 늦습니다.")

        instrument = self.bar_repository.select_instrument({"market": market, "symbol": symbol})
        if not instrument:
            # 종목 마스터가 비어 있는 이유를 먼저 답한다 — 국내는 키가 없어 마스터 적재 자체가
            # 안 됐고, 그건 "없는 종목"이 아니라 "아직 못 받은 종목"이다.
            reason, code = self._unavailable(args.get("workspace_id"), market, "instrument_master")
            if reason:
                return self._empty(market, symbol, "1d", reason, code)
            raise self._missing_instrument_error(market, symbol)

        rows, total = self.bar_repository.select_daily_bar_list(
            {
                "instrument_id": instrument["instrument_id"],
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit,
            }
        )
        rows = self._fold_to_regular(market, instrument["instrument_id"], rows)
        source, adj_policy, asof = self._provenance(rows)
        return {
            "items": [self._to_item(row) for row in rows],
            "total_count": total,
            "market": market,
            "symbol": symbol,
            "interval": "1d",
            "source": source,
            "adj_policy": adj_policy,
            "session_scope": self._session_scope(rows),
            "asof": asof,
            **_unavailable_fields(None if rows else self._empty_unavailable(args, market, symbol, "daily_bar", "일봉")),
        }

    def _fold_to_regular(self, market: str, instrument_id: int, rows: list[dict]) -> list[dict]:
        """분봉이 덮는 날의 일봉을 **정규장 창으로 접어** 갈아 끼운다 (#255 리드 결정 A′).

        저장은 안 건드린다 — 소스 일봉은 그대로 두고 **물어볼 때** 접는다. 적재 시점에 접었다가
        시계열이 날짜끼리 갈리고·장중 반쪽 캔들이 굳어 되돌린 자리다.

        접지 **않는** 날이 셋이다:

        - **세션이 아직 안 끝난 날** — 접으면 반쪽 캔들이 나온다
        - **세션 경계를 못 믿는 날** — 수능일. 캘린더가 2021년 이후를 모른다(`session_bounds` 가 `None`)
        - **정규장 창에 분봉이 없는 날** — 접을 것이 없다

        안 접은 날은 소스 값과 `session_scope` 를 그대로 둔다. 한 구간에 두 종류가 섞이면
        `_session_scope` 가 `mixed` 로 답한다 — 뭉개지 않는 것이 이 설계의 값이다.
        """
        if not rows:
            return rows

        now = market_local_naive(market, dt.datetime.now(dt.UTC))
        foldable: dict[str, tuple[dt.datetime, dt.datetime]] = {}
        for row in rows:
            day = dt.date.fromisoformat(str(row["time"]))
            bounds = session_bounds(market, day)
            if bounds is None or now <= bounds[1]:
                continue
            foldable[row["time"]] = bounds
        if not foldable:
            return rows

        spans = list(foldable.values())
        minute_rows, _ = self.bar_repository.select_minute_bar_list(
            {
                "instrument_id": instrument_id,
                "ts_from": min(start for start, _ in spans),
                "ts_to": max(end for _, end in spans),
                "limit": self.MINUTE_FOLD_LIMIT,
            }
        )
        if not minute_rows:
            return rows

        by_day: dict[str, list[dict]] = {}
        for minute in minute_rows:
            by_day.setdefault(str(minute["time"])[:10], []).append(minute)

        folded: list[dict] = []
        for row in rows:
            bounds = foldable.get(row["time"])
            bar = fold_regular_session(by_day.get(row["time"], []), bounds) if bounds else None
            if bar is None:
                folded.append(row)
                continue
            folded.append({**row, **bar, "session_scope": "regular"})
        return folded

    def select_minute_bar_list(self, args: dict) -> dict:
        market, symbol = args["market"].upper(), args["symbol"].upper()
        ts_from, ts_to = args["ts_from"], args["ts_to"]
        interval_min = int(args.get("interval_min") or 1)
        limit = self._validated_limit(args.get("limit"))
        if ts_from > ts_to:
            raise BadRequestError("ts_from 이 ts_to 보다 늦습니다.")
        if interval_min not in SYNTHESIZABLE_INTERVALS:
            allowed = ", ".join(str(i) for i in SYNTHESIZABLE_INTERVALS)
            raise BadRequestError(f"지원하지 않는 분봉 주기입니다: {interval_min} (가능: {allowed})")

        instrument = self.bar_repository.select_instrument({"market": market, "symbol": symbol})
        if not instrument:
            reason, code = self._unavailable(args.get("workspace_id"), market, "instrument_master")
            if reason:
                return self._empty(market, symbol, f"{interval_min}m", reason, code)
            raise self._missing_instrument_error(market, symbol)

        # 합성 주기는 1분봉 N개를 접어 1개를 만든다 — 상한도 그만큼 넉넉히 읽어야 한다.
        rows, total = self.bar_repository.select_minute_bar_list(
            {
                "instrument_id": instrument["instrument_id"],
                "ts_from": ts_from,
                "ts_to": ts_to,
                # `_validated_limit` 이 이미 limit <= MAX_BARS 를 강제한다 — 그래서 종전의
                # min(limit*interval_min, MAX_BARS*interval_min) 은 항상 왼쪽이었다(죽은 min).
                # 오른쪽을 MAX_BARS 로 줄이는 것은 틀린 고침이다: 60분봉 5000개를 83개로 자른다.
                "limit": limit * interval_min,
            }
        )
        source, adj_policy, asof = self._provenance(rows)
        items = [self._to_item(row) for row in rows]
        if interval_min > 1:
            items = synthesize_bars(items, interval_min)
            total = len(items)
        return {
            "items": items[:limit],
            "total_count": total,
            "market": market,
            "symbol": symbol,
            "interval": f"{interval_min}m",
            "source": source,
            "adj_policy": adj_policy,
            # 분봉에는 이 축이 없다 — **계산된 척하지 않는다.** 「접었다/안 접었다」는 일봉의
            # 성질이고, 분봉은 원본 그대로다.
            "session_scope": None,
            "asof": asof,
            **_unavailable_fields(
                None if items else self._empty_unavailable(args, market, symbol, "minute_bar", "분봉")
            ),
        }

    def find_gaps(self, args: dict) -> dict:
        """캘린더 세션과 적재본의 차집합 (MD-AD-23). 저장하지 않고 매 호출 계산한다 — 이중 장부를
        만들지 않기 위해서다. 결측(빠진 거래일)과 휴장(원래 없는 날)이 여기서 갈린다."""
        market, symbol = args["market"].upper(), args["symbol"].upper()
        date_from, date_to = args["date_from"], args["date_to"]
        if date_from > date_to:
            raise BadRequestError("date_from 이 date_to 보다 늦습니다.")

        instrument = self._instrument(market, symbol)
        # 상장 전·상장폐지 후는 애초에 거래일이 아니다 — 종목 마스터의 기간으로 먼저 좁힌다.
        if instrument.get("listed_dt"):
            date_from = max(date_from, instrument["listed_dt"])
        if instrument.get("delisted_dt"):
            date_to = min(date_to, instrument["delisted_dt"])
        if date_from > date_to:
            return {
                "items": [],
                "total_count": 0,
                "market": market,
                "symbol": symbol,
                "date_from": args["date_from"].isoformat(),
                "date_to": args["date_to"].isoformat(),
            }

        sessions = sessions_between(market, date_from, date_to)
        traded = set(
            self.bar_repository.select_traded_dates(
                {
                    "instrument_id": instrument["instrument_id"],
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        gaps = [session for session in sessions if session not in traded]
        return {
            "items": [gap.isoformat() for gap in gaps],
            "total_count": len(gaps),
            "market": market,
            "symbol": symbol,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

    def _empty_unavailable(
        self, args: dict, market: str, symbol: str, data_kind: str, label: str
    ) -> tuple[str, str | None]:
        """행이 0건일 때만 부르는 사유 조립 — "소스가 없다"가 "아직 안 받았다"보다 앞선다."""
        reason, code = self._unavailable(args.get("workspace_id"), market, data_kind)
        if reason:
            return reason, code
        return f"{market} {symbol} 의 해당 기간 {label}이 아직 적재되지 않았습니다", None

    @staticmethod
    def _validated_limit(limit) -> int:
        value = int(limit) if limit is not None else MAX_BARS
        if value <= 0 or value > MAX_BARS:
            raise BadRequestError(f"limit 은 1 이상 {MAX_BARS} 이하여야 합니다: {value}")
        return value

    @staticmethod
    def _to_item(row: dict) -> dict:
        return {
            "time": row["time"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": int(row["volume"]),
            "trade_value": row.get("trade_value"),
        }

    @staticmethod
    def _empty(market: str, symbol: str, interval: str, reason: str, code: str | None) -> dict:
        return {
            "items": [],
            "total_count": 0,
            "market": market,
            "symbol": symbol,
            "interval": interval,
            "source": None,
            "adj_policy": None,
            "asof": None,
            "unavailable_reason": reason,
            "unavailable_code": code,
        }


def fold_regular_session(minute_items: list[dict], bounds: tuple[dt.datetime, dt.datetime]) -> dict | None:
    """그 날의 1분봉을 **정규장 창만** 접어 일봉 하나로 만든다. 창 안에 아무것도 없으면 `None`.

    소스 일봉이 08:01–20:00 을 덮는 종목이 있어(#255 실측: 표본 25종목 중 9종목) 그 종가로
    체결하면 **정규장에서 낼 수 없는 가격**이 된다. 창 밖 분봉을 버리는 것이 이 함수의 일이다.

    경계는 **양쪽 포함**이다 — 15:30 종가단일가 체결이 그 창의 마지막 값이라 빼면 종가가 바뀐다.
    """
    start, end = bounds
    inside = [item for item in minute_items if start <= dt.datetime.fromisoformat(item["time"]) <= end]
    if not inside:
        return None
    volume = sum(int(item["volume"]) for item in inside)
    values = [item.get("trade_value") for item in inside]
    return {
        "time": start.date().isoformat(),
        "open": inside[0]["open"],
        "high": max(item["high"] for item in inside),
        "low": min(item["low"] for item in inside),
        "close": inside[-1]["close"],
        "volume": volume,
        # 거래대금은 합계다 — 하나라도 모르면 합계를 지어내지 않는다.
        "trade_value": None if any(v is None for v in values) else sum(values),
    }


def synthesize_bars(items: list[dict], interval_min: int) -> list[dict]:
    """1분봉을 N분봉으로 접는다 (PRD 가정 — "5·15·30·60분봉은 1분봉에서 합성, 별도 적재하지 않는다").

    버킷 경계는 **정각 기준**(예: 5분봉은 09:00·09:05…)이다. 첫 캔들 시각을 기준으로 잡으면 같은
    구간을 언제 조회하느냐에 따라 버킷이 밀려 결과가 달라진다 — 그건 재현성 문제다(NFR-006).
    거래대금은 합계다 — 겹치지 않는 별개 거래의 합이라 캔들 병합(MD-AD-24 의 max)과 규칙이 다르다.
    """
    buckets: dict[dt.datetime, dict] = {}
    order: list[dt.datetime] = []
    for item in items:
        ts = dt.datetime.fromisoformat(item["time"])
        bucket_ts = ts.replace(minute=(ts.minute // interval_min) * interval_min, second=0, microsecond=0)
        current = buckets.get(bucket_ts)
        if current is None:
            order.append(bucket_ts)
            buckets[bucket_ts] = {**item, "time": bucket_ts.strftime("%Y-%m-%dT%H:%M")}
            continue
        current["high"] = max(current["high"], item["high"])
        current["low"] = min(current["low"], item["low"])
        current["close"] = item["close"]
        current["volume"] += int(item["volume"])
        if item.get("trade_value") is not None:
            current["trade_value"] = (current.get("trade_value") or 0) + item["trade_value"]
    return [buckets[ts] for ts in order]


def _unavailable_fields(pair: tuple[str, str | None] | None) -> dict:
    """`(사유, 코드)` 또는 `None` 을 응답 필드 두 개로 편다 — 한쪽만 싣는 실수를 구조로 막는다."""
    if pair is None:
        return {"unavailable_reason": None, "unavailable_code": None}
    reason, code = pair
    return {"unavailable_reason": reason, "unavailable_code": code}
