#!/usr/bin/env python3
"""백테스트 엔진이 **저장소를 모르는 것**을 강제한다 — fail-closed (stdlib 전용).

## 왜 필요한가

스펙 §6 의 실측:

    20×20=400조합 · KR 전종목 10년(686만 bar)
      로드 1회 + 인메모리 400회  →  약 4.9분
      조합마다 DB 재조회         →  약 83분     ← I/O 가 계산의 16배

**「로드 1회 + 인메모리 N회」를 주석으로 부탁하면 지켜지지 않는다.** 조합 루프 안에서
캔들을 다시 읽는 코드는 돌아가기는 하므로 테스트가 잡지 못하고, 느려진 뒤에야 드러난다.

그래서 엔진 층이 **저장소·세션·HTTP 를 아예 import 하지 못하게** 한다. 다시 읽으려면
이 층 밖으로 나가야 하고, 나가는 것은 리뷰에서 보인다.

## 무엇을 금지하나

`app/services/backtest/` 안에서:
  · `*_repository` / `Repository` 이름의 import 나 속성 접근
  · `sqlalchemy` · `psycopg` · DB 세션
  · `httpx` · `requests` (외부 호출도 루프 안에서는 같은 병목이다)

`numpy` · `pandas` · `polars` · `duckdb` 도 막는다 — **의존성을 들이는 것은 리드 결정**이고
(스펙: `backend-service` 에 그것들이 없다), 몰래 들어오면 배포 크기와 빌드가 조용히 바뀐다.

    cd backend-service && uv run python scripts/verify_backtest_engine_purity.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ENGINE_DIR = BACKEND / "app" / "services" / "backtest"

# **순수해야 하는 것은 계산 층뿐이다.**
#
# 같은 폴더의 `*_service.py` 는 반대로 저장소를 알아야 한다 — 캔들을 읽어 넘기고 결과를
# 쓰는 것이 그 층의 일이다. 폴더 전체를 막으면 배선할 자리가 없어진다.
#
# 목록으로 두는 이유: 글롭(`*_service.py` 제외)으로 하면 새 계산 파일이 이름을 어떻게 짓느냐에
# 따라 조용히 검사에서 빠진다. **여기 없는 파일이 폴더에 생기면 실패**시켜, 새 파일마다 어느
# 쪽인지 사람이 정하게 한다.
PURE_FILES = ("engine.py", "metrics.py", "grid.py")

# 이 아래로 내려가면 파일이 사라졌거나 이름이 바뀐 것이다.
MIN_FILES = 1

# **첫 세그먼트만 보면 뚫린다.** 리뷰가 짚은 자리다 —
# `from app.core.database import SessionLocal` 은 루트가 `app` 이고
# `from services.bar.bar_service import BarService` 는 `services` 라, 아래 목록에도
# `_repository` 패턴에도 안 걸려 그물이 초록으로 통과했다.
#
# 그래서 **전체 경로**로도 본다. 이 층은 앱의 다른 어느 층도 알면 안 된다.
FORBIDDEN_PREFIXES = (
    "app.core.database",
    "app.core.container",
    "core.database",
    "core.container",
    "app.repositories",
    "repositories",
    "app.services",
    "services",
    "app.routers",
    "routers",
    "app.models",
    "models",
)

FORBIDDEN_MODULES = {
    "sqlalchemy": "저장소 접근 — 캔들은 호출자가 메모리에 올려서 넘긴다",
    "psycopg": "저장소 접근 — 같은 이유",
    "httpx": "외부 호출 — 조합 루프 안에서는 DB 와 같은 병목이다",
    "requests": "외부 호출 — 같은 이유",
    "numpy": "의존성 추가는 리드 결정이다 (backend-service 에 없다)",
    "pandas": "의존성 추가는 리드 결정이다",
    "polars": "의존성 추가는 리드 결정이다",
    "duckdb": "의존성 추가는 리드 결정이다",
}


def scan(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(BACKEND).as_posix()
    out: list[str] = []

    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            root = name.split(".")[0]
            if root in FORBIDDEN_MODULES:
                out.append(f"{rel}:{node.lineno} — `{name}` 금지: {FORBIDDEN_MODULES[root]}")
            if root.endswith("_repository") or "repositories" in name.split("."):
                out.append(f"{rel}:{node.lineno} — `{name}` 금지: 엔진은 저장소를 모른다")
            # **계산 층끼리는 서로 알아도 된다** — `grid` 가 `engine` 을 부르는 것이
            # 이 설계의 핵심이다. 금지하는 것은 「계산 층이 앱의 **다른** 층을 아는 것」이다.
            if any(
                name == f"services.backtest.{pure[:-3]}"
                or name.startswith(f"services.backtest.{pure[:-3]}.")
                or name == f"app.services.backtest.{pure[:-3]}"
                for pure in PURE_FILES
            ):
                continue

            # 전체 경로 — 첫 세그먼트만 보면 `app.core.database` 같은 우회가 통과한다.
            for prefix in FORBIDDEN_PREFIXES:
                if name == prefix or name.startswith(prefix + "."):
                    out.append(
                        f"{rel}:{node.lineno} — `{name}` 금지: 엔진은 앱의 다른 층을 모른다 (캔들은 호출자가 넘긴다)"
                    )
                    break

        # self.*_repository 속성 접근
        if isinstance(node, ast.Attribute) and node.attr.endswith("_repository"):
            out.append(f"{rel}:{node.lineno} — `.{node.attr}` 금지: 엔진은 저장소를 모른다")

    return out


def main() -> int:
    if not ENGINE_DIR.is_dir():
        print(f"::error::엔진 폴더가 없다: {ENGINE_DIR} — 경로가 바뀌었으면 이 검사도 고쳐라", file=sys.stderr)
        return 1

    present = {p.name for p in ENGINE_DIR.rglob("*.py") if p.name != "__init__.py"}
    files = sorted(ENGINE_DIR / name for name in PURE_FILES if (ENGINE_DIR / name).is_file())
    problems: list[str] = []
    for path in files:
        problems.extend(scan(path))

    # 분류되지 않은 파일 — 새 파일이 생기면 어느 쪽인지 사람이 정한다.
    unclassified = sorted(present - set(PURE_FILES) - {p.name for p in ENGINE_DIR.glob("*_service.py")})
    for name in unclassified:
        problems.append(
            f"app/services/backtest/{name} 이 분류되지 않았다 — 계산 층이면 PURE_FILES 에 넣고, "
            "저장소를 아는 층이면 `*_service.py` 로 이름 지어라"
        )

    missing = [name for name in PURE_FILES if not (ENGINE_DIR / name).is_file()]
    for name in missing:
        problems.append(f"PURE_FILES 의 {name} 가 없다 — 지웠거나 옮겼으면 목록에서도 빼라")

    print(
        f"`{ENGINE_DIR.relative_to(BACKEND)}` 의 계산 층 {len(files)}개 파일 검사 "
        f"(서비스 층 {len(list(ENGINE_DIR.glob('*_service.py')))}개는 저장소를 알아도 된다) · "
        f"위반 {len(problems)}건"
    )

    if len(files) < MIN_FILES:
        print(f"::error::검사 대상이 {len(files)}건뿐이다 — 그물이 죽어 있다 (하한 {MIN_FILES})", file=sys.stderr)
        return 1

    if problems:
        for line in problems:
            print(f"::error::{line}", file=sys.stderr)
        print(
            "\n엔진은 캔들을 넘겨받기만 한다. 다시 읽어야 한다면 이 층 밖(서비스)에서 읽어라 — "
            "조합 루프 안의 재조회가 계산보다 16배 비싸다 (스펙 §6).",
            file=sys.stderr,
        )
        return 1

    print("판정: 엔진이 저장소·외부호출·미승인 의존성을 모른다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
