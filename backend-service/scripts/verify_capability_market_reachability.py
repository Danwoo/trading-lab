#!/usr/bin/env python3
"""「받을 수 있다」고 선언한 시장을 그 소스가 정말 받아 주는지 확인한다 (#351).

## 왜 이 그물이 있나

화면의 「지금 받을 수 있는 것」에 오른 8개 시장 중 2개가 **눌러도 영영 0행**이었다.

    AMEX   sec  · instrument_master → succeeded · 0행 · 건너뜀 2736
    KONEX  toss · instrument_master → failed · HTTP 400

둘 다 원인이 같다 — **어댑터가 시장 목록을 손으로 적었다.** `sec` 은 매퍼가 만들 수 없는
`AMEX` 를 표에 실었고(소스의 `exchange` 어휘에 `NYSE American`·`NYSE MKT`·`NYSE Arca` 가
한 건도 없다), `toss` 는 소스가 400 으로 거절하는 `KONEX` 를 실었다. 선언과 현실이 갈려도
**눌러 보기 전에는 아무 데서도 안 드러났다.**

`capabilities()` 는 「이 소스가 이 시장에 무엇을 줄 수 있나」를 데이터로 노출해 화면이 이유를
보여 주게 하는 장치다(FR-021). 줄 수 없는 것을 `available=True` 로 실으면 그 장치가 반대로
작동한다 — 고른 사람은 「내가 뭘 잘못했나」로 읽는다.

## 무엇을 확인하나 (기본 모드 — 네트워크·DB·키 없이 돈다)

1. **표는 한 곳에서 나온다** — 어댑터마다 `MARKETS` 상수가 있고, `capabilities()` 가 내는
   시장 집합이 그것과 **같다.** 두 벌이면 곧 갈린다.
2. **약속한 시장은 물어볼 수 있는 시장이다** — 마스터를 약속한 칸(`available=True` 이거나
   「키를 넣으면 열립니다」)마다 `list_instruments(market)` 이 그 시장을 거절하지 않는다.
   키를 안 주고 부르므로 거절(`ProviderResponseInvalid`)과 키 없음(`ProviderKeyMissing`)이
   갈린다 — 네트워크까지 가지 않는다.
3. **모르는 시장은 거절한다** — 마스터를 약속하는 소스는 표 밖 시장을 빈 목록이 아니라
   사유로 돌려준다. 빈 목록은 「0건 적재 성공」으로 기록돼 이유를 지운다.
4. **`sec` 의 매핑표에 죽은 키가 없다** — `MARKET_BY_SEC_EXCHANGE` 의 키가 전부 소스가 실제로
   내보내는 표기여야 하고, `MARKETS` 는 그 표의 값에서 뽑혀야 한다. 죽은 키 하나가 값(시장)을
   살아 있는 것처럼 보이게 만든 것이 #351 의 AMEX 였다.
5. **소스가 말한 시장 목록 밖을 받아 주지 않는다** — 소스가 허용 목록을 스스로 답하는 곳
   (지금은 `toss`)에 한해, 어댑터가 받아 주는 시장이 그 목록 안에 있는지 본다.

**정적 검사가 못 막는 것**: 소스가 목록을 안 말하는 곳(예: `sec` 이 어느 날 AMEX 를 내보내기
시작하는 것)은 여기서 안 드러난다. 그 축은 아래 `--live` 가 맡는다.

**fail-closed**: 소스를 0개 읽었거나 검사 칸이 0건이면 실패한다. 검사한 건수를 항상 출력한다.

    cd backend-service && uv run python scripts/verify_capability_market_reachability.py

## `--live` — 실제로 눌러 본다

선언과 **실제 적재 결과**가 어긋나지 않는지는 소스를 눌러 봐야 안다. 자격이 있는 기계에서:

    cd backend-service/app && APP_ENV=development \\
      uv run python ../scripts/verify_capability_market_reachability.py --live

마스터를 약속한 시장마다 `list_instruments` 를 한 번씩 부르고 행 수를 낸다. **0행이면
실패**다 — 그것이 화면이 광고한 것과 어긋나는 유일한 상태다. 조회만 하고 아무것도 쓰지 않는다.
CI 는 자격이 없으므로 이 모드를 돌리지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 어댑터를 import 하면 `core.config` 가 뜬다 — `.env.development` 는 로컬에만 있으므로
# 러너에서도 같은 결과가 나오도록 최소값을 채운다 (다른 verify_* 스크립트와 같은 관례).
os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
for _key in (
    "BACKEND_SQL_DB_DRIVER",
    "BACKEND_SQL_DB_HOST",
    "BACKEND_SQL_DB_NAME",
    "BACKEND_SQL_DB_USER",
    "BACKEND_SQL_DB_PASSWORD",
    "SFTP_HOST",
    "SFTP_USERNAME",
    "SFTP_PASSWORD",
):
    os.environ.setdefault(_key, "x")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "1433")
os.environ.setdefault("SFTP_PORT", "22")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from importlib import import_module  # noqa: E402

from providers import get_provider, list_sources  # noqa: E402
from providers.base import (  # noqa: E402
    CREDENTIAL_MISSING_HINT,
    ProviderKeyMissing,
    ProviderResponseInvalid,
)

#: 자격의 **모양**만 맞춘 더미 — 이걸 넣으면 「키가 없어 막힘」이 사라져 표에 무엇이 남는지
#: 보인다. 값은 어디로도 나가지 않는다 (이 모드는 네트워크를 쓰지 않는다).
DUMMY_CREDENTIAL = "verify@example.com:DUMMY"

#: 표에 절대 없어야 하는 시장 이름 — 「모르는 시장은 거절한다」를 두드리는 값.
NOT_A_MARKET = "ZZ_NOT_A_MARKET"

#: 어댑터가 「이 시장은 안 다룬다」를 말할 때 쓰는 말. 어휘를 하나로 두어야 이 그물이
#: 거절과 다른 실패(키 없음·응답 이상)를 가를 수 있다.
UNHANDLED_MARKET_PHRASE = "시장을 다루지 않습니다"

#: SEC `company_tickers_exchange.json` 이 실제로 내보내는 `exchange` 어휘.
#: 실측 2026-08-23 (10,403행): Nasdaq 4365 · NYSE 3302 · OTC 2504 · None 198 · CBOE 34.
#: **이 목록에 없는 키를 매핑표에 적으면 그 값이 「우리가 SEC 로 채울 수 있는 시장」인 척한다.**
#: 소스가 어휘를 늘리면 이 상수를 먼저 갱신한다 — 위 명령 한 줄로 다시 세면 된다.
SEC_EXCHANGE_VOCABULARY = frozenset({"nasdaq", "nyse", "otc", "cboe", "none"})

#: 소스가 **자기 입으로 말한** 시장 목록. 어댑터가 받아 주기로 한 시장이 여기 없으면, 그 요청은
#: 우리 코드를 통과해 소스에서 거절당한다 — 화면에는 「소스가 요청을 거절했습니다」로 남아
#: 우리 표의 잘못이 소스 장애처럼 읽힌다(#351 의 KONEX 가 그랬다).
#: 소스가 목록을 안 말하는 곳은 여기 없다 — 지어내면 이 그물이 자기 자신을 검사하게 된다.
SOURCE_MARKET_VOCABULARY: dict[str, frozenset[str]] = {
    # 실측 2026-08-23 — `stocks/all` 이 그 밖의 값에 HTTP 400 과 함께 이 목록을 직접 답한다:
    # "유효하지 않은 market 입니다. KOSPI, KOSDAQ, NYSE, NASDAQ, AMEX 만 허용됩니다".
    "toss": frozenset({"KOSPI", "KOSDAQ", "NYSE", "NASDAQ", "AMEX"}),
}

FAILURES: list[str] = []


def _adapter_module(source: str):
    return import_module(f"providers.{source}.adapter")


def _promised_master_markets(source: str) -> list[str]:
    """마스터를 **약속한** 시장 — 지금 되거나, 키만 넣으면 되는 칸."""
    provider = get_provider(source, DUMMY_CREDENTIAL)
    out: list[str] = []
    for capability in provider.capabilities():
        if capability.data_kind != "instrument_master":
            continue
        reason = capability.reason or ""
        if capability.available or CREDENTIAL_MISSING_HINT in reason:
            out.append(capability.market)
    return sorted(set(out))


def _market_is_accepted(source: str, market: str) -> tuple[bool, str]:
    """`list_instruments(market)` 이 이 시장을 받아 주는가 — 키 없이 물어 네트워크를 안 탄다.

    거절(`ProviderResponseInvalid` + 「다루지 않습니다」)만 「안 받는다」다. 키 없음은
    「받지만 자격이 없다」이고, 그것은 이 검사의 관심사가 아니다.
    """
    provider = get_provider(source, None)
    try:
        asyncio.run(provider.list_instruments(market))
    except ProviderResponseInvalid as exc:
        if UNHANDLED_MARKET_PHRASE in str(exc):
            return False, "거절"
        return True, f"다른 응답 실패({exc})"
    except ProviderKeyMissing:
        return True, "키 없음(시장은 받음)"
    except Exception as exc:  # noqa: BLE001
        # 계약 밖 예외는 삼키지 않고 위반으로 올린다 — 여기서 터지면 이 그물이 통째로 죽어
        # 나머지 축을 아무것도 안 본 채 끝난다.
        FAILURES.append(
            f"{source} · {market}: list_instruments 가 계약 밖으로 터졌습니다 — {type(exc).__name__}: {exc}"
        )
        return True, f"계약 밖 예외({type(exc).__name__})"
    return True, "받음"


def check_table_has_one_source(sources: list[str]) -> int:
    """① `capabilities()` 의 시장 집합 == 어댑터의 `MARKETS`."""
    checked = 0
    for source in sources:
        module = _adapter_module(source)
        declared = getattr(module, "MARKETS", None)
        if declared is None:
            FAILURES.append(f"{source}: 어댑터 모듈에 MARKETS 상수가 없습니다 — 표의 출처가 코드에 안 보입니다")
            continue
        checked += 1
        from_table = {row.market for row in get_provider(source, DUMMY_CREDENTIAL).capabilities()}
        if from_table != set(declared):
            FAILURES.append(
                f"{source}: capabilities() 의 시장 {sorted(from_table)} 이 MARKETS {sorted(declared)} 와 다릅니다"
            )
    return checked


def check_promised_markets_are_reachable(sources: list[str]) -> int:
    """② 마스터를 약속한 시장은 `list_instruments` 이 받아 주는 시장이어야 한다."""
    checked = 0
    for source in sources:
        for market in _promised_master_markets(source):
            checked += 1
            accepted, how = _market_is_accepted(source, market)
            if not accepted:
                FAILURES.append(f"{source} · {market}: 마스터를 약속했는데 list_instruments 가 그 시장을 {how}합니다")
    return checked


def check_unknown_market_is_refused(sources: list[str]) -> int:
    """③ 마스터를 약속하는 소스는 표 밖 시장을 사유로 거절한다 (빈 목록 금지)."""
    checked = 0
    for source in sources:
        if not _promised_master_markets(source):
            # 마스터를 아무 시장에도 약속하지 않는 소스(정본이 남인 소스)는 이 축의 대상이 아니다.
            continue
        checked += 1
        accepted, how = _market_is_accepted(source, NOT_A_MARKET)
        if accepted:
            FAILURES.append(f"{source}: 표에 없는 시장 {NOT_A_MARKET!r} 을 거절하지 않습니다 ({how})")
    return checked


def check_sec_mapping_has_no_dead_keys() -> int:
    """④ `sec` 매핑표의 키가 전부 소스의 살아 있는 표기이고, `MARKETS` 가 그 값에서 나온다."""
    from providers.sec.adapter import MARKETS as sec_markets
    from providers.sec.mapper import MARKET_BY_SEC_EXCHANGE

    checked = 0
    for key in MARKET_BY_SEC_EXCHANGE:
        checked += 1
        if key.lower() not in SEC_EXCHANGE_VOCABULARY:
            FAILURES.append(
                f"sec: 매핑표의 키 {key!r} 를 소스가 내보낸 적이 없습니다 "
                f"(소스 어휘: {', '.join(sorted(SEC_EXCHANGE_VOCABULARY))}) — "
                f"이 키가 {MARKET_BY_SEC_EXCHANGE[key]!r} 를 받을 수 있는 시장인 척하게 만듭니다"
            )
    checked += 1
    derived = tuple(sorted(set(MARKET_BY_SEC_EXCHANGE.values())))
    if tuple(sec_markets) != derived:
        FAILURES.append(f"sec: MARKETS {tuple(sec_markets)} 가 매핑표에서 뽑은 {derived} 와 다릅니다")
    return checked


def check_accepted_markets_are_in_source_vocabulary(sources: list[str]) -> int:
    """⑤ 어댑터가 받아 주는 시장이 소스가 말한 목록 안에 있어야 한다 (소스가 목록을 말하는 곳만)."""
    checked = 0
    for source in sources:
        vocabulary = SOURCE_MARKET_VOCABULARY.get(source)
        if vocabulary is None:
            continue
        for market in getattr(_adapter_module(source), "MARKETS", ()):
            accepted, _how = _market_is_accepted(source, market)
            if not accepted:
                continue
            checked += 1
            if market not in vocabulary:
                FAILURES.append(
                    f"{source} · {market}: 어댑터는 받아 주는데 소스가 다루는 시장 목록"
                    f"({', '.join(sorted(vocabulary))})에 없습니다 — 요청이 소스에서 거절됩니다"
                )
    return checked


#: `--live` 호출 사이 간격(초). 소스마다 한도가 있고 여기서는 시장마다 새 어댑터를 만들므로
#: 어댑터 안의 조절기가 이어지지 않는다 — 이 간격이 없으면 429 가 판정을 흐린다(실측).
LIVE_CALL_INTERVAL_S = 5.0


def run_live(sources: list[str]) -> int:
    """`--live` — 약속한 시장을 실제로 눌러 행 수를 센다. 0행이면 실패.

    **자격이 없어 못 누른 칸은 실패가 아니라 건너뜀이다** — 「키를 넣으면 열립니다」는 아직
    약속이 아니라 안내이고, 키 없는 기계에서 그것까지 빨간불로 만들면 이 모드가 못 쓰게 된다.
    """
    import time

    from core.config import settings
    from services.data_key.data_key_service import DataKeyService

    data_key_service = DataKeyService(settings)
    checked = 0
    skipped: list[str] = []
    first = True
    print("\n--live: 약속한 마스터 시장을 실제로 눌러 본다")
    for source in sources:
        for market in _promised_master_markets(source):
            api_key = data_key_service.get_key(None, source)
            provider = get_provider(source, api_key)
            if not first:
                time.sleep(LIVE_CALL_INTERVAL_S)
            first = False
            try:
                rows = asyncio.run(provider.list_instruments(market))
            except ProviderKeyMissing:
                skipped.append(f"{source}·{market}")
                print(f"  SKIP {source:10} {market:8} 자격 없음 — 이 기계에서는 못 누른다")
                continue
            except Exception as exc:  # noqa: BLE001
                checked += 1
                FAILURES.append(f"{source} · {market}: 약속했는데 호출이 실패했습니다 — {type(exc).__name__}: {exc}")
                print(f"  FAIL {source:10} {market:8} {type(exc).__name__}")
                continue
            checked += 1
            if not rows:
                FAILURES.append(f"{source} · {market}: 약속했는데 0행입니다 — 화면이 광고한 것과 어긋납니다")
                print(f"  FAIL {source:10} {market:8} 0행")
                continue
            print(f"  OK   {source:10} {market:8} {len(rows)}행")
    if skipped:
        print(f"  (자격이 없어 건너뛴 칸 {len(skipped)}: {', '.join(skipped)})")
    return checked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--live", action="store_true", help="실제 소스를 눌러 행 수까지 확인한다 (자격 필요)")
    args = parser.parse_args(argv[1:])

    sources = list_sources()
    if not sources:
        print("::error::등록된 시세 소스가 0개입니다 — 검사 대상이 없으면 통과가 아니라 실패다")
        return 1

    table = check_table_has_one_source(sources)
    promised = check_promised_markets_are_reachable(sources)
    refused = check_unknown_market_is_refused(sources)
    sec_keys = check_sec_mapping_has_no_dead_keys()
    vocabulary = check_accepted_markets_are_in_source_vocabulary(sources)
    live = run_live(sources) if args.live else 0

    print(
        f"\n소스 {len(sources)}개({', '.join(sources)}) · MARKETS 대조 {table}개 · "
        f"약속한 마스터 시장 {promised}칸 · 모르는 시장 거절 {refused}개 · sec 매핑 키 {sec_keys}건 · "
        f"소스 어휘 대조 {vocabulary}칸" + (f" · --live 실호출 {live}칸" if args.live else "")
    )

    counts = {
        "MARKETS 대조": table,
        "약속한 마스터 시장": promised,
        "모르는 시장 거절": refused,
        "sec 매핑 키": sec_keys,
        "소스 어휘 대조": vocabulary,
    }
    if args.live:
        counts["--live 실호출"] = live
    empty = [name for name, count in counts.items() if count == 0]
    if empty:
        print(f"::error::검사 대상이 0건인 축이 있습니다: {', '.join(empty)} — fail-closed 종료")
        for failure in FAILURES:
            print(f"::error::  {failure}")
        return 1

    if FAILURES:
        print(f"::error::선언과 현실이 어긋난 곳 {len(FAILURES)}건")
        for failure in FAILURES:
            print(f"::error::  {failure}")
        print("::error::목록에 올리면 받을 수 있다는 뜻이다 — 못 받으면 목록이 거짓말을 한다 (#351)")
        return 1

    print("위반 0건 — 선언한 시장은 전부 그 소스가 받아 주는 시장이다")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
