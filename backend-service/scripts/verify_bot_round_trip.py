"""봇을 실제 Postgres 에 저장하고 그대로 다시 읽는지 검증한다 (#150 B0).

**왜 필요한가**: `tests/test_bot_schema_sql_consistency.py` 는 마이그레이션과 raw SQL 의 **이름**만
대조한다. 타입 불일치·SQL 문법·JSONB 바인딩·트랜잭션 경계는 DB 가 붙어야 드러난다. 그 중에서도
`CAST(:params AS jsonb)` 처럼 **DB 에 닿기 전엔 아무도 틀렸다고 말해 주지 않는 자리**가 이
모듈의 실질 위험이라, 레포지토리를 그대로 태워 왕복시킨다.

전제: `alembic upgrade head` 로 `public` 스키마가 서 있는 DB. CI 의 `test: backend` 잡이
바로 그 상태를 만든다 — 그래서 이 스크립트는 그 잡에 붙는다.

실행: `uv run python scripts/verify_bot_round_trip.py --i-know-this-drops-tables` (cwd=backend-service).
대상은 `BOT_ROUND_TRIP_DB_URL` 또는 기본 `postgresql://ci:ci@localhost:5432/ci`.
**이 스크립트는 자기가 만든 워크스페이스의 봇만 지운다** — 다른 데이터는 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("APP_ENV", "test")

from repositories.bot.bot_repository import BotRepository  # noqa: E402

DB_URL = os.getenv("BOT_ROUND_TRIP_DB_URL", "postgresql://ci:ci@localhost:5432/ci")
# 로컬 DB 를 실수로 겨누는 것을 막는다 — 다른 verify_*.py 와 같은 규율.
_SAFE_HOSTS = ("localhost", "127.0.0.1")

WORKSPACE_ID = 990150  # 이 스크립트 전용. 실데이터와 겹치지 않게 큰 값을 쓴다.
ACTOR = "bot-round-trip@ci.local"

failures: list[str] = []
checked = 0


def check(condition: bool, message: str) -> None:
    global checked
    checked += 1
    if condition:
        print(f"  ok   {message}")
    else:
        failures.append(message)
        print(f"  FAIL {message}")


def _engine():
    url = DB_URL if DB_URL.startswith("postgresql+") else DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    # 레포 규약 — 바인드 파라미터 값이 예외 메시지·로그로 새지 않게 한다
    # (tests/test_sql_parameter_hiding.py 가 전수 강제). 제약 이름은 그대로 보이므로
    # 아래 유니크·CHECK 단언은 영향을 받지 않는다.
    return create_engine(url, hide_parameters=True)


def _bot_args(name: str) -> dict:
    return {
        "workspace_id": WORKSPACE_ID,
        "bot_nm": name,
        "bot_desc": "왕복 검증용",
        "combine_rule": "SCORE",
        "universe_kind": "LIST",
        "universe_ref": {"tickers": ["005930", "AAPL"]},
        "alloc_per_symbol": 1000000.0,
        "max_positions": 5,
        "stop_loss_pct": 7.5,
        "take_profit_pct": 20.0,
        "max_trades_per_day": 3,
        "bot_role": "PROPOSE",
        "use_at": "Y",
        # 실험대 스펙 §8.6.3 — 설정마다 출처가 남는다
        "param_sources": {"stop_loss_pct": "AI_SUGGESTED", "max_positions": "USER"},
        "reg_id": ACTOR,
    }


STRATEGIES = [
    {
        "strategy_key": "ma_pullback",
        "params": {"ma_period": 20, "pullback_pct": 3.0, "recover_confirm": True},
        "param_sources": {"ma_period": "AI_SUGGESTED"},
        "weight": 1.5,
    },
    {
        "strategy_key": "surge_exclusion",
        "params": {"lookback_days": 5, "surge_pct": 20.0, "measure": "high"},
        "param_sources": {},
        "weight": None,
    },
]


def run(repository: BotRepository, engine) -> None:
    (bot_id,) = repository.insert_bot(_bot_args("왕복 검증 봇"), STRATEGIES)
    check(isinstance(bot_id, int) and bot_id > 0, f"INSERT 가 bot_id 를 돌려준다 ({bot_id})")

    bot = repository.select_bot({"workspace_id": WORKSPACE_ID, "bot_id": bot_id})
    check(bot is not None, "저장한 봇이 조회된다")
    if bot is None:
        return

    check(bot["bot_nm"] == "왕복 검증 봇", "이름이 그대로다")
    check(bot["combine_rule"] == "SCORE" and bot["universe_kind"] == "LIST", "결합·유니버스가 그대로다")
    check(bot["bot_role"] == "PROPOSE", "봇 신원(bot_role)이 그대로다")
    # 숫자 컬럼은 Numeric 이라 CAST 없이 읽으면 Decimal 이 나온다 — 레포지토리가 float 로 캐스팅한다.
    check(
        isinstance(bot["stop_loss_pct"], float) and abs(bot["stop_loss_pct"] - 7.5) < 1e-9,
        f"손절률이 float 7.5 로 온다 ({bot['stop_loss_pct']!r})",
    )
    check(bot["max_positions"] == 5, "최대 종목수가 그대로다")
    # 여기가 이 스크립트의 핵심 — CAST(:x AS jsonb) 바인딩이 실제로 도는지.
    check(
        bot["universe_ref"] == {"tickers": ["005930", "AAPL"]}, f"JSONB 가 dict 로 왕복한다 ({bot['universe_ref']!r})"
    )
    check(
        bot["param_sources"] == {"stop_loss_pct": "AI_SUGGESTED", "max_positions": "USER"},
        f"설정 출처가 그대로다 ({bot['param_sources']!r})",
    )
    check(bot["reg_id"] == ACTOR and bot["reg_dt"] is not None, "감사 컬럼이 채워진다")

    rows = repository.select_bot_strategy_list({"bot_id": bot_id})
    check(len(rows) == 2, f"실린 전략이 2건이다 ({len(rows)}건)")
    check([row["strategy_key"] for row in rows] == ["ma_pullback", "surge_exclusion"], "전략 순서가 보존된다")
    check(rows[0]["params"] == STRATEGIES[0]["params"], f"전략 파라미터가 JSONB 로 왕복한다 ({rows[0]['params']!r})")
    check(rows[0]["param_sources"] == {"ma_period": "AI_SUGGESTED"}, "전략별 출처가 그대로다")
    check(rows[0]["weight"] == 1.5 and rows[1]["weight"] is None, "가중치가 그대로다 (없으면 None)")
    check([row["sort_order"] for row in rows] == [0, 1], "정렬 순서가 0부터 매겨진다")

    # 같은 이름은 워크스페이스 안에서 유일하다 — 목록에서 구분이 안 되기 때문.
    try:
        repository.insert_bot(_bot_args("왕복 검증 봇"), STRATEGIES)
    except Exception as error:  # noqa: BLE001 — 드라이버 예외 종류가 아니라 제약 이름을 본다
        check(
            "uq_tn_bot_workspace_nm" in str(error), f"같은 이름 재등록이 유니크 제약에 걸린다 ({type(error).__name__})"
        )
    else:
        check(False, "같은 이름 재등록이 유니크 제약에 걸린다")

    # CHECK 제약이 어휘 밖 값을 실제로 막는가 (스키마·서비스 목록과 대조만으로는 안 드러난다).
    bad = _bot_args("어휘 밖 봇")
    bad["combine_rule"] = "XOR"
    try:
        repository.insert_bot(bad, STRATEGIES)
    except Exception as error:  # noqa: BLE001
        check(
            "ck_tn_bot_combine_rule" in str(error), f"어휘 밖 combine_rule 이 CHECK 에 걸린다 ({type(error).__name__})"
        )
    else:
        check(False, "어휘 밖 combine_rule 이 CHECK 에 걸린다")

    # 전략 목록 교체 — 부분 갱신이 아니라 통째로 갈아 끼운다.
    update = _bot_args("왕복 검증 봇 (수정)")
    update["bot_id"] = bot_id
    update["mod_id"] = ACTOR
    repository.update_bot(update, [STRATEGIES[1]])
    rows = repository.select_bot_strategy_list({"bot_id": bot_id})
    check([row["strategy_key"] for row in rows] == ["surge_exclusion"], f"전략 목록이 통째로 갈린다 ({rows})")

    items, total = repository.select_bot_list(
        {"workspace_id": WORKSPACE_ID, "skip": 0, "take": 10, "filter": None, "sort": None}
    )
    check(total == 1 and items[0]["bot_id"] == bot_id, f"목록 조회가 1건을 센다 (total={total})")

    repository.delete_bot({"workspace_id": WORKSPACE_ID, "bot_id": bot_id})
    check(repository.select_bot({"workspace_id": WORKSPACE_ID, "bot_id": bot_id}) is None, "삭제되면 조회되지 않는다")
    with engine.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM tn_bot_strategy WHERE bot_id = :bot_id"), {"bot_id": bot_id}
        ).scalar()
    check(left == 0, f"실린 전략이 ON DELETE CASCADE 로 함께 지워진다 (남은 {left}건)")


def cleanup(engine) -> None:
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("DELETE FROM tn_bot WHERE workspace_id = :ws"), {"ws": WORKSPACE_ID})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--i-know-this-drops-tables", action="store_true")
    args = parser.parse_args()

    if not any(host in DB_URL for host in _SAFE_HOSTS):
        print(f"대상이 로컬이 아니다: {DB_URL}", file=sys.stderr)
        return 1
    if not args.i_know_this_drops_tables:
        print("--i-know-this-drops-tables 플래그가 없습니다 (전용 워크스페이스의 봇 행 삭제 동의).", file=sys.stderr)
        return 1

    engine = _engine()
    repository = BotRepository(engine)
    print(f"대상 DB: {DB_URL} · 워크스페이스 {WORKSPACE_ID}")
    cleanup(engine)
    try:
        run(repository, engine)
    finally:
        cleanup(engine)

    # 검사 0건은 통과가 아니다 — 스키마가 안 서 있거나 run() 이 일찍 빠져나간 경우를 잡는다.
    print(f"\n검사 {checked}건 · 실패 {len(failures)}건")
    if checked < 18:
        print(f"::error::검사가 {checked}건뿐이다 (기대 18건 이상) — 왕복이 중간에 끊겼다", file=sys.stderr)
        return 1
    if failures:
        for message in failures:
            print(f"  · {message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
