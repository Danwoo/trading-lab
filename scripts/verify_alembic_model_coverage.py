#!/usr/bin/env python3
"""마이그레이션이 만든 우리 테이블이 **드리프트 검사 밖에 남는 것**을 막는다 — fail-closed.

## 왜 필요한가

`alembic/env.py` 의 `include_object` 는 「내 모델에 대응이 없는 DB 테이블은 남의 것」으로 보고
비교에서 뺀다. 다른 서비스 테이블과 남의 `alembic_version` 이 섞이는 것을 막으려는 **옳은 규칙**
이고, 그 대가도 주석에 적혀 있다.

그런데 대가가 하나 더 있다: **우리 테이블인데 ORM 모델에 안 올린 것도 함께 빠진다.** 그러면
그 테이블은 컬럼이 사라져도 `alembic check` 가 조용히 통과한다 — 드리프트 그물이 그 테이블에
대해서는 아예 없는 것과 같다.

실제로 그랬다: `tn_bot`·`tn_bot_strategy` 가 마이그레이션(`0014_bot.py`)에만 있고 모델에는
없었다. 옆 스텝(`verify_bot_round_trip.py`)이 대신 잡고 있어 인스턴스는 급하지 않았지만,
**「이름 필터가 없다」는 클래스**가 남아 다음 테이블에서 되풀이된다.

## 무엇을 하나

마이그레이션이 `create_table("tn_…")` 로 만든 우리 테이블 목록과 ORM 메타데이터의 테이블
목록을 대조해, **모델에 없는 것**을 낸다. 사유가 있으면 `EXEMPT` 에 이유와 함께 적는다.

    python3 scripts/verify_alembic_model_coverage.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend-service"
VERSIONS = BACKEND / "alembic" / "versions"
SCHEMA = BACKEND / "app" / "models" / "schema.py"

# 우리 테이블 접두 — `TN_`(일반)·`TC_`(코드)·`BA_`(인증). 소문자로 비교한다.
OUR_PREFIXES = ("tn_", "tc_", "ba_")

# 모델에 없어도 되는 것 — **이유를 적는다.** 빈 사유는 등록으로 치지 않는다.
EXEMPT: dict[str, str] = {
    # 이 둘은 `verify_bot_round_trip.py`(alembic-drift 잡의 옆 스텝)가 컬럼·제약·CASCADE 를
    # 22건으로 직접 검사한다 — 지금은 그쪽이 대신 지킨다. 모델로 올리는 것이 정본이지만
    # (CHECK 4종·유니크 2종·JSONB 기본값을 정확히 옮겨야 한다) 그것은 별건이다.
    # **면제는 「안 봐도 된다」가 아니라 「다른 그물이 본다」는 선언이다.**
    "tn_bot": "verify_bot_round_trip.py 가 22건으로 검사한다 — 모델 승격은 별건",
    "tn_bot_strategy": "verify_bot_round_trip.py 가 22건으로 검사한다 — 모델 승격은 별건",
}

# 마이그레이션이 이 아래로 줄면 글롭이 어긋난 것이다.
MIN_MIGRATIONS = 5


def tables_in_migrations() -> dict[str, str]:
    """`create_table("tn_…")` 로 만들어진 우리 테이블 → 그것을 만든 마이그레이션 파일."""
    found: dict[str, str] = {}
    files = sorted(VERSIONS.glob("*.py"))
    if len(files) < MIN_MIGRATIONS:
        raise SystemExit(
            f"::error::마이그레이션을 {len(files)}건 수집했다 (하한 {MIN_MIGRATIONS}) — "
            "글롭이 어긋났는지 보라"
        )
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name != "create_table" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                table = first.value.lower()
                if table.startswith(OUR_PREFIXES):
                    found.setdefault(table, path.name)
    return found


def tables_in_models() -> set[str]:
    """ORM 메타데이터가 아는 테이블 — `__tablename__` 을 AST 로 읽는다."""
    tree = ast.parse(SCHEMA.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", None) == "__tablename__" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            names.add(node.value.value.lower())
    return names


def main() -> int:
    migrated = tables_in_migrations()
    modeled = tables_in_models()
    uncovered = {
        t: src for t, src in migrated.items() if t not in modeled and t not in EXEMPT
    }

    print(
        f"마이그레이션이 만든 우리 테이블 {len(migrated)}건 검사 · 모델 등재 "
        f"{len(migrated) - len(uncovered) - len(EXEMPT)}건 · 면제 {len(EXEMPT)}건 · 미등재 {len(uncovered)}건"
    )

    if not modeled:
        print(
            "::error::모델에서 테이블을 한 건도 못 읽었다 — 그물이 죽어 있다",
            file=sys.stderr,
        )
        return 1

    if uncovered:
        for table, source in sorted(uncovered.items()):
            print(
                f"::error::{table} 이 ORM 모델에 없다 ({source}) — alembic 이 이 테이블을 "
                "「남의 것」으로 보고 드리프트 비교에서 뺀다. 컬럼이 사라져도 check 가 통과한다.",
                file=sys.stderr,
            )
        print(
            "\napp/models/schema.py 에 모델을 올리거나, 올리지 않을 이유가 있으면 "
            "이 스크립트의 EXEMPT 에 사유와 함께 적으세요.",
            file=sys.stderr,
        )
        return 1

    print("판정: 우리 테이블이 전부 드리프트 검사 안에 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
