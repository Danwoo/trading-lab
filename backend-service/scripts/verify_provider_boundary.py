"""provider 경계 검증 — 소스 이름이 `providers/<소스>/` 밖으로 새지 않는지 (fail-closed).

구현설계 §5.2 #1 이 정한 규율을 검출 가능한 형태로 못 박는다. 어댑터를 하나 더 붙일 때 소비자
코드가 따라 바뀌면 provider 추상화는 이름만 남는다 — 그 순간을 이 스크립트가 잡는다.

**왜 오더 원문의 grep 을 그대로 쓰지 않는가**: 오더는
`git grep -nE "from providers\\.[a-z_]+" -- services repositories routers` 를 제시하는데, 이
정규식은 계약 모듈(`providers.models`·`providers.base`)까지 잡는다. 그 둘은 소스가 아니라
정규화 모델·Protocol 이라 소비자가 import 해도 경계 위반이 아니다. 그래서 이 스크립트는
**파일시스템에서 실제 소스 패키지 목록을 읽어** 그 이름만 금지한다 — 소스가 늘면 검사 대상도
저절로 는다.

**fail-closed 3중**:
1. 스캔 대상 디렉터리가 하나라도 없으면 실패 (경로가 옮겨졌는데 조용히 0건이 되는 것을 막는다)
2. 소스 패키지가 0개면 실패 (`providers/` 가 비면 검사가 무의미한데 초록이 된다)
3. 스캔한 파이썬 파일이 0개면 실패

검사한 개수를 항상 출력한다 — 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이
구분할 수 있게.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROVIDERS_DIR = _BACKEND_DIR / "app" / "providers"

# 소비자 계층 — 여기서 소스 패키지를 import 하면 위반이다.
CONSUMER_DIRS = ("app/services", "app/repositories", "app/routers", "app/managers")

# 소스가 아니라 계약인 모듈 — 소비자가 import 해도 무방하다.
CONTRACT_MODULES = {"base", "models", "merge"}


def source_packages() -> list[str]:
    """`providers/` 밑의 소스 패키지 이름 목록 (디렉터리이면서 계약 모듈이 아닌 것)."""
    return sorted(
        entry.name
        for entry in _PROVIDERS_DIR.iterdir()
        if entry.is_dir() and not entry.name.startswith(("_", ".")) and entry.name not in CONTRACT_MODULES
    )


def main() -> int:
    if not _PROVIDERS_DIR.is_dir():
        print(f"::error::providers 디렉터리가 없습니다: {_PROVIDERS_DIR} — fail-closed 종료")
        return 1

    sources = source_packages()
    if not sources:
        print(f"::error::{_PROVIDERS_DIR} 에서 소스 패키지를 0건 수집했습니다 — fail-closed 종료")
        print("::error::어댑터가 이동·삭제됐거나 폴더 규칙이 바뀌었을 수 있습니다. 확인하세요.")
        return 1

    missing = [name for name in CONSUMER_DIRS if not (_BACKEND_DIR / name).is_dir()]
    if missing:
        print(f"::error::스캔 대상 디렉터리가 없습니다: {', '.join(missing)} — fail-closed 종료")
        return 1

    pattern = re.compile(r"^\s*(?:from|import)\s+providers\.(" + "|".join(re.escape(s) for s in sources) + r")\b")

    scanned = 0
    violations: list[str] = []
    for directory in CONSUMER_DIRS:
        for path in sorted((_BACKEND_DIR / directory).rglob("*.py")):
            scanned += 1
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.match(line):
                    violations.append(f"{path.relative_to(_BACKEND_DIR)}:{lineno}: {line.strip()}")

    if scanned == 0:
        print(f"::error::{', '.join(CONSUMER_DIRS)} 에서 파이썬 파일을 0건 수집했습니다 — fail-closed 종료")
        return 1

    print(f"소스 패키지 {len(sources)}개: {', '.join(sources)}")
    print(f"소비자 계층 파이썬 파일 {scanned}개 검사 (대상 디렉터리 {len(CONSUMER_DIRS)}개)")

    if violations:
        print(f"::error::provider 경계 침범 {len(violations)}건 — 소스 이름이 providers/ 밖으로 샜습니다")
        for violation in violations:
            print(f"::error::  {violation}")
        print("::error::소비자는 `providers.get_provider(source, key)` 로만 어댑터를 얻습니다.")
        return 1

    print("provider 경계 위반 0건 — 소비자는 어느 소스인지 모른다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
