"""#315 — 봇을 지웠을 때 **무엇이 함께 사라지고 무엇이 남는지**를 스키마로 못박는다.

화면(`frontend/components/features/Bot/deleteBotWithConfirm.tsx`)이 지우기 전에 두 문장을
말한다: 「실린 전략은 함께 지워진다」·「검증 기록은 남지만 어느 봇의 것인지 가리키지 못하게
된다」. 그 문구의 근거는 마이그레이션의 FK 유무 하나뿐이다.

- `tn_bot_strategy.bot_id` → `tn_bot.bot_id` **ON DELETE CASCADE** — 그래서 함께 사라진다.
- `tn_backtest_run.bot_id` → FK **없음**(0015_backtest, 의도된 설계) — 그래서 삭제를 막지도
  않고 지우지도 않는다. 행은 남고 `bot_id` 만 가리킬 곳을 잃는다.

둘 중 하나라도 뒤집히면 화면 문구가 **거짓말이 된다.** 되돌릴 수 없는 조작의 안내가 틀리는
것은 조작부가 없는 것보다 나쁘다 — 사용자가 그 문장을 믿고 누르기 때문이다.

이 그물이 못 잡는 것: 실제 DB 의 드리프트. 여기서 초록이라고 개발·운영 DB 가 이 마이그레이션과
같다는 뜻은 아니다 (`test_alembic_head_freshness.py` 와 같은 경계).

실행: `uv run python tests/test_bot_delete_cascade_boundary.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"
BOT_MIGRATION = VERSIONS / "0014_bot.py"
BACKTEST_MIGRATION = VERSIONS / "0015_backtest.py"
BOT_REPOSITORY = ROOT / "app" / "repositories" / "bot" / "bot_repository.py"
CONFIRM_UI = ROOT.parent / "frontend" / "components" / "features" / "Bot" / "deleteBotWithConfirm.tsx"


def _table_body(source: str, table: str) -> str:
    match = re.search(rf'op\.create_table\(\s*"{table}"(?P<body>.*?)\n    \)', source, re.S)
    assert match, f"{table} 의 create_table 을 못 찾았다 — 이 그물은 죽어 있다"
    return match.group("body")


def test_bot_strategy_cascades_with_its_bot() -> None:
    """실린 전략은 봇과 함께 사라진다 — 화면이 그렇게 말한다."""
    body = _table_body(BOT_MIGRATION.read_text(encoding="utf-8"), "tn_bot_strategy")
    fk = re.search(r'sa\.ForeignKey\(\s*"tn_bot\.bot_id"\s*,\s*ondelete="(?P<action>\w+)"', body)
    assert fk, "tn_bot_strategy.bot_id 의 tn_bot FK 를 못 찾았다"
    assert fk.group("action") == "CASCADE", f"ondelete 가 CASCADE 가 아니다: {fk.group('action')}"


def test_backtest_run_does_not_reference_bot() -> None:
    """검증 실행은 봇을 FK 로 가리키지 않는다 — 그래서 삭제가 막히지도, 실행이 지워지지도 않는다."""
    source = BACKTEST_MIGRATION.read_text(encoding="utf-8")
    body = _table_body(source, "tn_backtest_run")
    assert re.search(r'sa\.Column\(\s*"bot_id"', body), "tn_backtest_run.bot_id 컬럼이 없다"
    assert "tn_bot.bot_id" not in source, (
        "tn_backtest_run 이 tn_bot 을 FK 로 가리키기 시작했다 — "
        "삭제가 막히거나 실행이 함께 지워진다. 화면 확인 문구를 그 결과로 고쳐라."
    )


def test_delete_bot_sql_touches_only_the_bot_table() -> None:
    """리포지토리가 DB 제약 말고 손으로 지우는 것을 늘리면 문구와 실제가 갈린다."""
    source = BOT_REPOSITORY.read_text(encoding="utf-8")
    match = re.search(r"def delete_bot\(self.*?\n    def ", source, re.S)
    assert match, "delete_bot 본문을 못 찾았다 — 이 그물은 죽어 있다"
    deleted = set(re.findall(r"DELETE FROM (\w+)", match.group(0)))
    assert deleted == {"tn_bot"}, f"delete_bot 이 지우는 테이블이 tn_bot 하나가 아니다: {sorted(deleted)}"


def test_confirm_text_states_both_outcomes() -> None:
    """확인 문구가 두 결과를 갈라 말한다 — 한쪽만 적으면 나머지가 조용해진다."""
    assert CONFIRM_UI.is_file(), f"확인 문구 파일이 없다: {CONFIRM_UI}"
    text = CONFIRM_UI.read_text(encoding="utf-8")
    for phrase in ("되돌릴 수 없습니다", "함께 지워집니다", "검증 기록은 남지만"):
        assert phrase in text, f"확인 문구에서 '{phrase}' 가 사라졌다"


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    assert tests, "검사 대상 0건 — fail-closed"
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests)}건 검사 · 실패 {failures}건")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
