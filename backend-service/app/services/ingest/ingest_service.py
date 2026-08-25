"""적재 오케스트레이션 — 소스가 무엇인지 모르는 워커의 두뇌.

이 서비스가 아는 것은 정규화 모델과 우리 테이블뿐이다. 어느 소스인지는 `get_provider(source, key)`
로 레지스트리에 물어보는 문자열 하나이며, `providers.<소스>` 를 import 하지 않는다 — 어댑터를
하나 더 붙여도 이 파일은 바뀌지 않는다(AC-4).

**심볼 해석의 소유자가 여기다.** `NormalizedBar.symbol`·`market` 을 `tn_instrument` 로
`instrument_id` 에 매핑하고, 매핑되지 않는 심볼은 **버리지 않고** `skipped_rows` 로 센다 —
조용히 사라진 행은 나중에 "왜 적은가"를 답할 수 없다.

**한도 소진은 조용히 실패하지 않는다**(NFR-007): 어댑터가 `RateLimitExhausted` 를 올리면 지금까지
받은 것을 커밋하고 `status='rate_limited'` + `cursor` 를 남긴다. 다음 실행이 그 지점부터 이어받는다.
"""

import datetime as dt
from contextlib import contextmanager
from decimal import Decimal

from core.exceptions import BadRequestError
from core.logger import logger
from fastapi.concurrency import run_in_threadpool
from providers import get_alias_resolver, get_provider, list_alias_sources
from providers.base import ProviderKeyMissing, ProviderResponseInvalid, RateLimitExhausted
from providers.failure import describe_provider_failure
from providers.models import NormalizedBar, NormalizedInstrument
from repositories.ingest.ingest_repository import IngestRepository
from services.data_key.data_key_service import DataKeyService
from utils.redaction.redactor import redact_secrets

# 종목 마스터 적재 뒤 별칭을 붙여 볼 소스. 없으면 그냥 건너뛴다 — 별칭은 있으면 좋은 것이지
# 적재 성공의 조건이 아니다.
ALIAS_ENRICH_SOURCE = "openfigi"

# 별칭 매핑을 시도할 종목 수 상한. OpenFIGI 익명 한도가 분당 25요청 × 요청당 10잡이라
# 전 종목(수천)을 붙이면 몇 시간이 걸린다 — 그 사실을 숫자로 못 박고, 넘는 만큼은 건너뛴 뒤
# 로그로 남긴다(조용히 자르지 않는다).
ALIAS_ENRICH_LIMIT = 100


class IngestService:
    def __init__(self, ingest_repository: IngestRepository, data_key_service: DataKeyService):
        self.ingest_repository = ingest_repository
        self.data_key_service = data_key_service

    # ── 잡 큐 ────────────────────────────────────────────────────────────────
    def enqueue(self, args: dict) -> int:
        market, symbols = parse_scope(args["job_kind"], args["scope"])
        if args["job_kind"] != "instrument_master" and not symbols:
            raise BadRequestError("캔들 적재는 scope 에 종목이 있어야 합니다 (예: 'NASDAQ:AAPL,MSFT')")
        logger.info(f"적재 잡 등록 — {args['source']}/{args['job_kind']} scope={market}:{len(symbols)}종목")
        return self.ingest_repository.insert_ingest_run(args)

    def select_ingest_run_list(self, args: dict) -> tuple[list, int]:
        return self.ingest_repository.select_ingest_run_list(args)

    def claim_next_queued_run(self) -> dict | None:
        if not self.ingest_repository.try_advisory_lock():
            logger.info("적재 잡 폴링 건너뜀 — 다른 실행이 잠금을 쥐고 있습니다")
            return None
        return self.ingest_repository.claim_next_queued_run()

    # ── 실행 ─────────────────────────────────────────────────────────────────
    async def run_job(self, run: dict) -> dict:
        """잡 하나를 끝까지 실행하고 결과를 `tn_ingest_run` 에 적는다. 예외를 밖으로 올리지
        않는다 — 잡의 실패는 워커의 실패가 아니라 그 행의 상태다."""
        run_id, source, job_kind = run["run_id"], run["source"], run["job_kind"]
        api_key = self.data_key_service.get_key(run.get("workspace_id"), source)
        written = skipped = 0
        try:
            provider = get_provider(source, api_key)
            if job_kind == "instrument_master":
                written, skipped = await self._run_instrument_master(run, provider)
            elif job_kind == "daily_bar":
                written, skipped = await self._run_daily_bar(run, provider)
            elif job_kind == "minute_bar":
                written, skipped = await self._run_minute_bar(run, provider)
            else:
                raise BadRequestError(f"모르는 job_kind 입니다: {job_kind}")
        except RateLimitExhausted as exc:
            # 받은 것은 이미 커밋돼 있다 — 여기서는 재개 지점만 남긴다.
            await self._finish(run_id, "rate_limited", cursor=exc.cursor, failed_reason=str(exc))
            logger.warning(f"적재 잡 {run_id} 한도 소진 — 재개 지점 {exc.cursor}")
            return {"status": "rate_limited", "cursor": exc.cursor}
        except (ProviderKeyMissing, ProviderResponseInvalid, BadRequestError) as exc:
            # 우리 예외라고 그대로 적지 않는다 — 어댑터가 상태 코드를 옮겨 담은 사유는 무엇이
            # 일어났는지에서 멈춘다(`공급자 응답이 유효하지 않습니다: Alpaca 응답 상태 403`).
            reason = redact_secrets(describe_provider_failure(exc, source))[:1000]
            await self._finish(run_id, "failed", failed_reason=reason)
            logger.warning(f"적재 잡 {run_id} 실패: {exc}")
            return {"status": "failed", "failed_reason": reason}
        except Exception as exc:  # noqa: BLE001 — 잡 하나의 실패가 워커를 죽이지 않게 한다
            logger.exception(f"INGEST_JOB_ERROR run_id={run_id} source={source}")
            # 어댑터가 변환하지 못하고 그대로 올라온 예외다. **원문을 화면에 싣지 않는다** —
            # `httpx.HTTPStatusError` 문자열에는 요청 URL 이 통째로 들어 있고 data.go.kr 은
            # 인증키를 쿼리로 받는다. 기술 원문은 바로 위 `logger.exception` 이 가져간다.
            reason = redact_secrets(describe_provider_failure(exc, source))[:1000]
            await self._finish(run_id, "failed", failed_reason=reason)
            return {"status": "failed", "failed_reason": reason}

        await self._finish(run_id, "succeeded", written_rows=written, skipped_rows=skipped, cursor="")
        logger.info(f"적재 잡 {run_id} 완료 — 기록 {written}행, 건너뜀 {skipped}행")
        return {"status": "succeeded", "written_rows": written, "skipped_rows": skipped}

    async def _finish(self, run_id: int, status: str, **fields) -> None:
        """잡의 마지막 상태를 남긴다.

        **스레드풀로 넘긴다.** 이 매니저는 앱 안에서 도는 백그라운드 워커(`--workers=1`)라,
        동기 DB 호출이 이벤트 루프를 막으면 **그 순간 이 앱의 모든 HTTP 요청이 함께 멈춘다** —
        적재는 장중에 돌고 그때 화면이 응답을 기다린다.
        """
        await run_in_threadpool(
            self.ingest_repository.update_ingest_run_status,
            # aware 로 준다 (#359) — naive 파라미터는 서버가 **세션 tz** 로 읽는데 값은 **OS 시계**라,
            # 앱 컨테이너가 KST(compose 의 TZ)이고 세션이 UTC 인 조합에서 9시간 어긋난다.
            {"run_id": run_id, "status": status, "finished_dt": dt.datetime.now(dt.UTC), **fields},
        )

    async def _run_instrument_master(self, run: dict, provider) -> tuple[int, int]:
        market, _ = parse_scope(run["job_kind"], run["scope"])
        instruments = await provider.list_instruments(market)
        skipped = len(getattr(provider, "last_skipped", []))
        written = await run_in_threadpool(
            self.ingest_repository.upsert_instruments,
            [_instrument_row(instrument) for instrument in instruments],
            run["source"],
        )
        # 종목 마스터를 먼저 확정해 둔다 — 뒤이은 별칭 단계가 실패해도 "몇 건 썼는지"가 남는다.
        await run_in_threadpool(
            self.ingest_repository.update_ingest_run_status,
            {"run_id": run["run_id"], "status": "running", "written_rows": written, "skipped_rows": skipped},
        )
        skipped += await self._write_aliases(run, market, instruments)
        return written, skipped

    async def _write_aliases(self, run: dict, market: str, instruments: list[NormalizedInstrument]) -> int:
        """소스가 준 별칭 + (있으면) 식별자 매핑 소스의 별칭을 `tn_symbol_alias` 에 넣는다.

        반환값은 **넣지 못한 별칭 수**다 — 버린 것은 세어서 `skipped_rows` 로 올린다.
        """
        id_map = await run_in_threadpool(
            self.ingest_repository.select_instrument_id_map, market, [i.symbol for i in instruments]
        )
        today = dt.date.today()
        rows = [
            {
                "instrument_id": id_map[instrument.symbol],
                "alias_kind": kind,
                "alias_value": value,
                "valid_from": today,
            }
            for instrument in instruments
            if instrument.symbol in id_map
            for kind, value in instrument.aliases.items()
        ]

        if ALIAS_ENRICH_SOURCE in list_alias_sources():
            targets = [(market, instrument.symbol) for instrument in instruments][:ALIAS_ENRICH_LIMIT]
            if len(instruments) > ALIAS_ENRICH_LIMIT:
                logger.info(
                    f"별칭 매핑은 상한 {ALIAS_ENRICH_LIMIT}종목까지만 시도한다 "
                    f"(대상 {len(instruments)}종목 — 소스 한도상 전 종목은 별도 배치가 필요하다)"
                )
            try:
                resolver = get_alias_resolver(
                    ALIAS_ENRICH_SOURCE, self.data_key_service.get_key(run.get("workspace_id"), ALIAS_ENRICH_SOURCE)
                )
                resolved = await resolver.resolve_aliases(targets)
            except Exception:  # noqa: BLE001 — 별칭은 적재 성공의 조건이 아니다
                logger.exception("ALIAS_ENRICH_ERROR — 별칭 매핑 실패, 종목 마스터 적재는 유지")
                resolved = {}
            rows.extend(
                {
                    "instrument_id": id_map[symbol],
                    "alias_kind": kind,
                    "alias_value": value,
                    "valid_from": today,
                }
                for (_market, symbol), aliases in resolved.items()
                if symbol in id_map
                for kind, value in aliases.items()
            )

        rows, dropped = await self._drop_claimed_aliases(rows)
        if rows:
            await run_in_threadpool(self.ingest_repository.upsert_symbol_aliases, rows, run["source"])
        return dropped

    async def _drop_claimed_aliases(self, rows: list[dict]) -> tuple[list[dict], int]:
        """부분 유니크(MD-AD-25)가 거절할 별칭을 **삽입 전에** 걸러 낸다.

        두 갈래를 막는다 — ① 같은 배치 안에서 같은 `(kind, value)` 가 두 종목에 붙는 경우,
        ② 다른 종목이 이미 그 값을 현재값으로 쥐고 있는 경우. 둘 다 정상적으로 일어난다:
        SEC 의 CIK 는 **회사 단위**라 GOOGL·GOOG 같은 복수 클래스가 같은 CIK 를 공유한다.

        건너뛴 것은 조용히 사라지지 않고 `skipped_rows` 로 셈해진다 — "별칭이 왜 이것만 있나"를
        나중에 물을 수 있어야 한다. 어느 종목이 그 값을 갖느냐는 **먼저 온 쪽**이다(소스 순서).
        """
        if not rows:
            return [], 0
        owners = await run_in_threadpool(
            self.ingest_repository.select_current_alias_owners,
            [(row["alias_kind"], row["alias_value"]) for row in rows],
        )
        kept: list[dict] = []
        claimed: dict[tuple[str, str], int] = dict(owners)
        dropped = 0
        for row in rows:
            key = (row["alias_kind"], row["alias_value"])
            owner = claimed.get(key)
            if owner is not None and owner != row["instrument_id"]:
                dropped += 1
                continue
            claimed[key] = row["instrument_id"]
            kept.append(row)
        if dropped:
            logger.info(f"별칭 {dropped}건은 이미 다른 종목의 현재값이라 건너뜀 (MD-AD-25 부분 유니크)")
        return kept, dropped

    async def _run_daily_bar(self, run: dict, provider) -> tuple[int, int]:
        market, symbols = parse_scope(run["job_kind"], run["scope"])
        id_map = await run_in_threadpool(self.ingest_repository.select_instrument_id_map, market, symbols)
        date_to = _as_date(run.get("period_to")) or dt.date.today()

        written = skipped = 0
        last_done = run.get("cursor") or ""
        for symbol in _resume_from(symbols, run.get("cursor")):
            instrument_id = id_map.get(symbol)
            if instrument_id is None:
                # 종목 마스터에 없는 심볼 — 버리지 않고 센다.
                skipped += 1
                last_done = symbol
                continue
            date_from = await self._daily_start_date(instrument_id, run)
            with _resume_at(last_done):
                bars = await provider.fetch_daily(symbol, market, date_from, date_to)
            skipped += len(getattr(provider, "last_skipped", []))
            rows = [_daily_row(bar, instrument_id, run) for bar in bars]
            written += await run_in_threadpool(self.ingest_repository.upsert_daily_bars, rows)
            last_done = symbol
            # 심볼 하나가 끝날 때마다 진행을 남긴다 — 한도에 걸려도 어디까지 왔는지가 남는다.
            await run_in_threadpool(
                self.ingest_repository.update_ingest_run_status,
                {
                    "run_id": run["run_id"],
                    "status": "running",
                    "cursor": symbol,
                    "written_rows": written,
                    "skipped_rows": skipped,
                },
            )
        return written, skipped

    async def _daily_start_date(self, instrument_id: int, run: dict) -> dt.date:
        """적재 시작일. **DB 상 마지막 저장 거래일을 항상 다시 포함한다**(MD-AD-22) — 장중에
        받은 반쪽 캔들이 정본에 영구히 남는 것을 upsert 로 덮어쓰기 위해서다.

        요청 구간(`period_from`)이 저장분보다 앞이면 **소급 적재를 요청한 것**이라 그것을 따른다.
        """
        period_from = _as_date(run.get("period_from"))
        last_saved = await run_in_threadpool(self.ingest_repository.select_last_trade_date, instrument_id)
        if last_saved is None:
            return period_from or dt.date.today() - dt.timedelta(days=365)
        if period_from is not None and period_from < last_saved:
            # 요청이 저장분보다 앞이면 **소급 적재를 요청한 것**이다. 그것을 버리면 화면이
            # `find_gaps` 로 보여준 결측을 메울 유일한 레버가 무음으로 죽는다 — 우회로도 없다.
            # MD-AD-22(마지막 저장일을 다시 받는다)는 **위쪽 끝**의 규칙이라 여기서 안 깨진다:
            # 시작이 더 앞이면 그 하루는 여전히 구간 안에 있다.
            return period_from
        return last_saved

    async def _require_minute_partition(self, date_from: dt.date, date_to: dt.date) -> None:
        """분봉 파티션이 요청 구간을 덮는지 — 마이그레이션 주석이 적은 그 확인이다.

        안 보면 psycopg 원문(`no partition of relation ... found for row`)이 그대로
        `failed_reason` 에 박힌다. 사용자가 읽을 문장이 아니고, 무엇을 하면 되는지도 없다.
        """
        if date_from > date_to:
            # 역전 구간은 파티션 판정 이전의 문제다 — 통과시키면 0건 적재가 「성공」으로 끝난다.
            raise BadRequestError(f"구간이 뒤집혀 있습니다 ({date_from} ~ {date_to}).")
        covered = await run_in_threadpool(self.ingest_repository.select_minute_partition_range)
        if covered is None:
            raise BadRequestError("분봉 파티션이 아직 없습니다 — 마이그레이션을 먼저 적용하세요.")
        low, high = covered
        # 파티션 상계는 배타적이다(`TO ('...')`) — 그 날짜 자체는 안 들어간다.
        if date_from < low or date_to >= high:
            raise BadRequestError(
                f"분봉을 저장할 파티션이 없는 구간입니다 ({date_from} ~ {date_to}). "
                f"지금 덮는 구간은 {low} ~ {high - dt.timedelta(days=1)} 입니다."
            )

    async def _run_minute_bar(self, run: dict, provider) -> tuple[int, int]:
        market, symbols = parse_scope(run["job_kind"], run["scope"])
        id_map = await run_in_threadpool(self.ingest_repository.select_instrument_id_map, market, symbols)
        date_from = _as_date(run.get("period_from")) or dt.date.today()
        date_to = _as_date(run.get("period_to")) or dt.date.today()
        await self._require_minute_partition(date_from, date_to)
        ts_from = dt.datetime.combine(date_from, dt.time.min)
        ts_to = dt.datetime.combine(date_to, dt.time.max)

        written = skipped = 0
        last_done = run.get("cursor") or ""
        for symbol in _resume_from(symbols, run.get("cursor")):
            instrument_id = id_map.get(symbol)
            if instrument_id is None:
                skipped += 1
                last_done = symbol
                continue
            # 저장 목적 호출은 언제나 1분봉이다 (MD-AD-26 — 다른 주기는 조회 시 합성한다).
            with _resume_at(last_done):
                bars = await provider.fetch_minute(symbol, market, ts_from, ts_to, 1)
            skipped += len(getattr(provider, "last_skipped", []))
            rows = [_minute_row(bar, instrument_id, run) for bar in bars]
            written += await run_in_threadpool(self.ingest_repository.upsert_minute_bars, rows)
            last_done = symbol
            await run_in_threadpool(
                self.ingest_repository.update_ingest_run_status,
                {
                    "run_id": run["run_id"],
                    "status": "running",
                    "cursor": symbol,
                    "written_rows": written,
                    "skipped_rows": skipped,
                },
            )
        return written, skipped


@contextmanager
def _resume_at(last_done: str):
    """어댑터가 올린 한도 예외의 `cursor` 를 **우리 재개 단위**(마지막으로 끝낸 심볼)로 바꾼다.

    설계(§7.2)는 "어댑터의 cursor 를 그대로 옮겨 적는다"고 썼는데, 실제로 돌려 보니 그러면
    **재개가 동작하지 않는다**(실측): 어댑터가 주는 문자열은 `daily_bar:NASDAQ:NVDA` 처럼 소스
    쪽 재개 지점이라 `_resume_from` 이 심볼 목록에서 찾지 못하고 매번 처음부터 다시 돈다. 그렇다고
    서비스가 그 문자열을 파싱하면 소스 표기가 서비스로 새어 들어온다(구현설계 §5.2 #1).

    그래서 저장하는 cursor 는 우리 어휘(심볼)로 두고, 어댑터가 준 원래 지점은 예외 메시지로만
    남긴다 — 설계의 의도("다음 실행이 이어받는다")를 지키면서 경계를 지킨다.
    """
    try:
        yield
    except RateLimitExhausted as exc:
        logger.info(f"어댑터 재개 지점 {exc.cursor!r} → 잡 재개 지점 {last_done!r} 로 환산")
        raise RateLimitExhausted(cursor=last_done) from exc


def parse_scope(job_kind: str, scope: str | None) -> tuple[str, list[str]]:
    """`"NASDAQ"` 또는 `"NASDAQ:AAPL,MSFT"` 를 `(market, symbols)` 로.

    형식이 어긋나면 빈 목록으로 넘어가지 않고 거절한다 — 잘못 적힌 scope 가 "0건 적재 성공"으로
    끝나면 아무도 눈치채지 못한다.
    """
    if not scope or not scope.strip():
        raise BadRequestError("scope 가 비어 있습니다")
    market, _, symbol_part = scope.strip().partition(":")
    market = market.strip().upper()
    if not market:
        raise BadRequestError(f"scope 에서 시장을 읽지 못했습니다: {scope!r}")
    symbols = [s.strip().upper() for s in symbol_part.split(",") if s.strip()]
    if job_kind == "instrument_master" and symbols:
        raise BadRequestError("instrument_master 잡의 scope 는 시장 하나입니다 (예: 'NASDAQ')")
    return market, symbols


def _resume_from(symbols: list[str], cursor: str | None) -> list[str]:
    """`cursor` 가 가리키는 심볼 **다음**부터 이어받는다. 커서가 목록에 없으면 처음부터 —
    scope 가 바뀐 잡을 억지로 이어붙이지 않는다."""
    if not cursor or cursor not in symbols:
        return symbols
    return symbols[symbols.index(cursor) + 1 :]


def _as_date(value) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _instrument_row(instrument: NormalizedInstrument) -> dict:
    return {
        "country": instrument.country,
        "market": instrument.market,
        "symbol": instrument.symbol,
        "issuer_nm": instrument.issuer_nm,
        "currency": instrument.currency,
        "sector_code": instrument.sector_code,
    }


def _daily_row(bar: NormalizedBar, instrument_id: int, run: dict) -> dict:
    return {
        "instrument_id": instrument_id,
        "trade_date": bar.ts.date(),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": int(bar.volume),
        "trade_value": bar.trade_value if isinstance(bar.trade_value, Decimal | type(None)) else None,
        "source": run["source"],
        "adj_policy": bar.adj_policy,
        # 소스가 준 일봉이 어느 구간을 덮는지 **우리는 모른다** — 소스마다, 같은 소스의
        # 종목마다 다르다(#255). 모르면 모른다고 적는다. 분봉으로 다시 만든 봉만 `regular` 다.
        "session_scope": "unknown",
        "ingest_run_id": run["run_id"],
    }


def _minute_row(bar: NormalizedBar, instrument_id: int, run: dict) -> dict:
    return {
        "instrument_id": instrument_id,
        "ts": bar.ts,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": int(bar.volume),
        "source": run["source"],
        "adj_policy": bar.adj_policy,
        "ingest_run_id": run["run_id"],
    }
