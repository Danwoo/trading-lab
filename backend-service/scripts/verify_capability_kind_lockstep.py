"""capability `data_kind` 어휘의 lockstep 검증 — 백엔드 어댑터 ↔ 프론트 상수 (fail-closed, stdlib 전용).

**왜 있나.** 프론트가 소스를 고를 때 `dataKind === "candles"` 를 찾고 있었다. 백엔드는 그 값을
한 번도 낸 적이 없다(`daily_bar`·`minute_bar`·…). 그래서 **적재 버튼이 영영 안 열렸다.** 그런데
프론트 테스트가 같은 가짜 값을 픽스처로 써서 **그물이 계속 초록**이었다 — 가짜 픽스처는 계약을
검사하지 않고 자기 자신을 검사한다.

이 스크립트가 잠그는 것:

1. 어댑터가 실제로 내는 `data_kind` 값 전부가 프론트 `DATA_KINDS` 에 있다
2. 프론트 `DATA_KINDS` 에만 있고 어댑터엔 없는 값이 없다 (지어낸 값 차단)
3. 프론트 코드·테스트가 `DATA_KINDS` 밖의 문자열을 `dataKind` 로 쓰지 않는다

**fail-closed**: 어댑터를 0개 읽었거나 상수를 못 찾으면 실패한다. 검사한 개수를 항상 출력한다.

실행: `cd backend-service && python3 scripts/verify_capability_kind_lockstep.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = _BACKEND_DIR.parent

PROVIDERS_DIR = REPO_ROOT / "backend-service" / "app" / "providers"
FRONT_CONST = REPO_ROOT / "frontend" / "schemas" / "terminal" / "ingest.ts"

#: 프론트에서 `dataKind` 에 문자열을 직접 박는 자리를 찾는다 (코드·테스트 둘 다).
FRONT_GLOBS = ("frontend/components/**/*.tsx", "frontend/services/**/*.ts", "frontend/tests/**/*.tsx")

DATA_KIND_IN_ADAPTER = re.compile(r'data_kind\s*=\s*"([a-z_]+)"')
DATA_KIND_IN_DICT = re.compile(r'^\s*"([a-z_]+)":\s*\(', re.MULTILINE)
FRONT_LIST = re.compile(r"export const DATA_KINDS = \[([^\]]*)\] as const", re.DOTALL)
FRONT_USAGE = re.compile(r'dataKind\s*(?:===|!==|:)\s*"([a-z_]+)"')


def adapter_kinds() -> tuple[set[str], int]:
    """어댑터가 내는 `data_kind` 값과 읽은 파일 수."""
    kinds: set[str] = set()
    files = sorted(PROVIDERS_DIR.glob("*/adapter.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        kinds.update(DATA_KIND_IN_ADAPTER.findall(text))
        # 토스처럼 dict 로 묶어 도는 어댑터 — `"daily_bar": (ok, reason)` 모양
        if "data_kind=kind" in text:
            kinds.update(DATA_KIND_IN_DICT.findall(text))
    return kinds, len(files)


def front_kinds() -> set[str]:
    match = FRONT_LIST.search(FRONT_CONST.read_text(encoding="utf-8"))
    if match is None:
        return set()
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def front_usages() -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for pattern in FRONT_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                for kind in FRONT_USAGE.findall(line):
                    out.append((str(path.relative_to(REPO_ROOT)), lineno, kind))
    return out


def main() -> int:
    for path in (PROVIDERS_DIR, FRONT_CONST):
        if not path.exists():
            print(f"::error::필수 경로가 없습니다: {path} — fail-closed 종료")
            return 1

    backend, adapter_count = adapter_kinds()
    if adapter_count == 0 or not backend:
        print(f"::error::어댑터 {adapter_count}개에서 data_kind 를 {len(backend)}건 읽었습니다 — fail-closed 종료")
        return 1

    front = front_kinds()
    if not front:
        print(f"::error::{FRONT_CONST} 에서 DATA_KINDS 를 못 읽었습니다 — fail-closed 종료")
        return 1

    usages = front_usages()
    failures: list[str] = []
    for missing in sorted(backend - front):
        failures.append(f"백엔드가 내는데 프론트 DATA_KINDS 에 없습니다: {missing!r}")
    for invented in sorted(front - backend):
        failures.append(f"프론트 DATA_KINDS 에만 있습니다 (어느 어댑터도 안 냅니다): {invented!r}")
    for relative, lineno, kind in usages:
        if kind not in backend:
            failures.append(f"{relative}:{lineno}: dataKind 에 없는 값 {kind!r} 을 씁니다")

    print(f"어댑터 {adapter_count}개 · 백엔드 data_kind {len(backend)}종: {', '.join(sorted(backend))}")
    print(f"프론트 DATA_KINDS {len(front)}종 · 프론트에서 dataKind 문자열을 쓰는 자리 {len(usages)}곳")

    if failures:
        print(f"::error::capability data_kind lockstep 위반 {len(failures)}건")
        for failure in failures:
            print(f"::error::  {failure}")
        print("::error::백엔드 어댑터가 SoT 다 — 프론트가 값을 지어내면 화면이 조용히 안 열린다.")
        return 1

    print("위반 0건 — 프론트와 백엔드가 같은 어휘를 쓴다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
