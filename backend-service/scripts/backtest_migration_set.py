"""backtest 테이블을 건드리는 마이그레이션을 **체인 순서대로** 고른다 — 두 검증 스크립트의 공용.

`verify_backtest_schema.py`(스펙 §6 컬럼 대조)와 `verify_backtest_run_persists.py`(서비스→DB
왕복)는 둘 다 마이그레이션을 **격리 스키마**에 `search_path` 로 태운다. 목록을 손으로 적지
않는 이유도 같다: 뒤에 붙는 리비전이 그 테이블을 건드리면 자동으로 따라와야 한다 — 한 파일을
핀으로 박으면 새 리비전이 영영 그물 밖에 남는다(0016 의 `tax` 컬럼이 실제로 그랬다).

**두 스크립트가 각자 이 로직을 갖고 있었다.** 같은 판정을 두 벌로 두면 갈린다 — 실제로 #359 의
`0019` 가 양쪽을 동시에 깨뜨렸고, 면제를 한쪽에만 적으면 다른 쪽만 빨간불로 남았을 것이다.

## 격리 스키마에서 못 도는 리비전

`search_path` 로 스키마를 갈아 끼우는 하네스라, **스키마를 명시 수식하는** 리비전은 구조적으로
못 돈다(`0013` 은 `public.tn_board` 를 SQL 에 직접 적는데, 그건 마커에 안 걸려 우연히 비껴갔다).
그런 리비전은 `EXEMPT` 에 **사유와 함께** 적는다.

**빈 사유는 등록으로 치지 않고, 낡은 항목은 실패한다** — 적힌 리비전이 사라지거나 더는 마커에
안 걸리면 목록이 거짓이 된 것이므로 조용히 통과시키지 않는다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"

#: 이 소스 문자열을 가진 리비전이 대상이다.
MIGRATION_MARKER = "tn_backtest"

EXEMPT: dict[str, str] = {
    "0019_timestamptz_audit_columns": (
        "전 DB 시각 컬럼 전환(#359) — public·frontend 를 명시 수식해 격리 스키마에서 돌 수 없고, "
        "backtest 테이블을 만들지도 않는다(감사 컬럼의 타입만 바꾼다). "
        "이 리비전은 alembic-drift(전 체인 + alembic check)와 verify_timestamptz_using.py 가 본다"
    ),
}


class BacktestMigrationSetError(RuntimeError):
    """대상 목록을 신뢰할 수 없다 — 통과가 아니라 실패다."""


def _load(path: Path, prefix: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{prefix}{path.stem}", path)
    if spec is None or spec.loader is None:
        raise BacktestMigrationSetError(f"리비전을 읽지 못했다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ordered_migrations(module_prefix: str = "_bt_mig_") -> list[ModuleType]:
    """대상 리비전 모듈을 체인 순서로. 목록이 미덥지 않으면 `BacktestMigrationSetError`."""
    blank = sorted(revision for revision, reason in EXEMPT.items() if not reason.strip())
    if blank:
        raise BacktestMigrationSetError(f"EXEMPT 에 사유 없는 항목이 있다: {', '.join(blank)}")

    modules: dict[str, ModuleType] = {}
    parents: dict[str, tuple[str, ...]] = {}
    exempted: set[str] = set()
    for path in sorted(VERSIONS.glob("[0-9]*.py")):
        if MIGRATION_MARKER not in path.read_text(encoding="utf-8"):
            continue
        module = _load(path, module_prefix)
        if module.revision in EXEMPT:
            exempted.add(module.revision)
            continue
        modules[module.revision] = module
        parent = getattr(module, "down_revision", None)
        # merge 리비전의 `down_revision` 은 **튜플**이다. 스칼라로만 다루면 그 튜플이 통째로
        # 키가 되어 어느 부모에도 안 걸리고, 부모보다 먼저 도는 순서가 나온다.
        parents[module.revision] = () if parent is None else (parent,) if isinstance(parent, str) else tuple(parent)

    stale = sorted(set(EXEMPT) - exempted)
    if stale:
        raise BacktestMigrationSetError(
            f"EXEMPT 에 적힌 리비전이 더는 마커('{MIGRATION_MARKER}')에 걸리지 않는다: "
            f"{', '.join(stale)} — 목록이 낡았으니 지우거나 사유를 고치세요"
        )
    if not modules:
        raise BacktestMigrationSetError(f"backtest 테이블을 다루는 마이그레이션을 0건 찾았다: {VERSIONS}")

    # 고른 것들끼리 체인 순서를 만든다 — 부모가 목록 밖이면 그것이 시작점이다.
    order: list[str] = []
    remaining = dict(modules)
    while remaining:
        ready = [rev for rev in remaining if all(p not in remaining for p in parents[rev])]
        if not ready:
            raise BacktestMigrationSetError(f"마이그레이션 순서를 정할 수 없다 (순환?): {sorted(remaining)}")
        for revision in sorted(ready):
            order.append(revision)
            del remaining[revision]

    print(f"태울 마이그레이션 {len(order)}건 · 면제 {len(exempted)}건 ({', '.join(sorted(exempted)) or '없음'})")
    return [modules[revision] for revision in order]


def ordered_migrations_or_exit() -> list[ModuleType] | None:
    """검증 스크립트용 얇은 껍데기 — 사유를 `::error::` 로 찍고 `None` 을 준다."""
    try:
        return ordered_migrations()
    except BacktestMigrationSetError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return None
