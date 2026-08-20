"""절대 날짜 리터럴 정적 스캔 — mock·계약 경로에 "시간이 지나면 저절로 낡는 고정값" 재유입 차단 (#269).

#228(연도 상한 하드코딩)·#235(픽스처 연도 고정)·#260(픽스처 날짜 고정)이 같은 부류로 3회 반복됐다.
주 게이트는 동작 기반 신선도 검사(각 서비스 tests/test_mock_freshness.py — 증상을 본다)이고,
이 스캔은 값싼 보조 그물이다 — 낡을 리터럴이 소스에 들어오는 순간을 잡는다.

대상 경로: */app/clients/** · */app/schemas/** (mock 픽스처·요청 경계가 사는 곳).
검사 3종 (AST 기반 — 주석·독스트링·경로 밖 파일의 정당한 날짜(#269 오탐 부류 a·b·c)는 구조적으로 제외):
  (1) 문자열 안 ISO 날짜        — "2026-06-02" (#260 형태)
  (2) 문자열 안 압축 8자리 날짜 — "20250314…"·"D20260620-…" 식별자 내장 포함 (#235 형태)
  (3) Field(...) 인자의 연도 정수 — le=2025, default=2024 (#228 형태)

의도적으로 잡지 않는 것:
  - 19xx 세기 — 설립일 등 "안 움직이는 과거 사실"(오탐 부류 d)이고, 낡음은 '최근'이 굳는 것이라
    20xx 이후만 잡는다. 20xx 의 정당한 과거 사실이 생기면 ALLOWLIST 에 사유와 함께 등록한다.
  - Field 밖 모듈 상수 연도 (MIN_BSNS_YEAR = 2015 — 업스트림 사실, 오탐 부류 e).
  - 문자열·Field 밖 정수 (금액·수량·volume 등 숫자 데이터).

fail-closed — **글롭마다 개별로** (#402):
  종전에는 fail-closed 가 두 글롭의 **합계 0건**에만 걸려 있었다. 그래서 목록의 원소 하나가
  통째로 사라져도 나머지가 0이 아니라 조용히 초록이었다 — 실증(#402): schemas 글롭을 없는
  경로로 바꾸자 19개 파일이 통째로 안 읽혔는데 `EXIT=0` 이고, 출력 문구는 손으로 쓴
  "(clients·schemas)" 그대로라 읽는 사람이 구분할 수 없었다. 디렉터리 이동·리네임으로
  **평범하게** 일어나는 일이다.
  지금은 글롭마다 파일 하한·서비스 하한을 선언하고(SCAN_TARGETS), 실제 수를 글롭별로 출력한다.
  출력 문구도 선언에서 생성한다 — 손으로 쓴 라벨은 대상이 줄어도 그대로이기 때문이다.
  파일을 정당하게 지웠다면 하한도 함께 내린다: 조용히 넘어가는 대신 시끄럽게 실패하는 것이 의도다.

stdlib 전용: `python3 scripts/verify_no_absolute_dates.py` (cwd 무관).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]


class ScanTarget(NamedTuple):
    """스캔 글롭 하나 + 그 글롭 **혼자서** 만족해야 하는 하한 (#402).

    min_files 는 그 글롭이 잡아야 할 파일 수, min_services 는 그 파일들이 걸쳐 있어야 할
    서비스 수다. 둘을 함께 두는 이유: 파일 하한만 있으면 "A 서비스의 clients 가 사라지고
    B 서비스에 그만큼 새 파일이 생긴" 상쇄를 못 잡는다.
    """

    glob: str
    label: str
    min_files: int
    min_services: int


# 하한은 현재 실측치다 (2026-08-06). 파일·서비스를 정당하게 지웠다면 여기도 함께 내린다.
SCAN_TARGETS: list[ScanTarget] = [
    ScanTarget("*/app/clients/**/*.py", "clients", min_files=29, min_services=9),
    ScanTarget("*/app/schemas/**/*.py", "schemas", min_files=19, min_services=10),
]

# 정당한 20xx 리터럴의 예외 등록처 — (레포 상대경로, 리터럴 정규식, 사유). 비우는 것이 기본이다.
ALLOWLIST: list[tuple[str, str, str]] = []

# (20|21)xx + 유효 월·일만 — 연도 뒤 아무 숫자나 날짜로 오독하지 않는다 (volume 19840000 등).
_ISO_DATE = re.compile(r"(?<!\d)(?:20|21)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)")
# 왼쪽 경계만 비숫자 요구 — "D20260620-…" 같은 접두 식별자와 "20250314000123" 같은
# 날짜+일련 연접은 잡고, "0320000310" 처럼 숫자열 중간에서 우연히 날짜로 읽히는 것은 제외.
_COMPACT_DATE = re.compile(r"(?<!\d)(?:20|21)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])")
_YEAR_RANGE = range(2000, 2200)


def _docstring_ids(tree: ast.AST) -> set[int]:
    """모듈·클래스·함수 독스트링 Constant 노드의 id 집합 — 설명 문서는 검사 대상이 아니다."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    ids.add(id(body[0].value))
    return ids


def _field_year_literals(tree: ast.AST) -> list[tuple[int, str]]:
    """Field(...) 호출 인자에 직접 박힌 연도 정수 — #228 의 le=2025·default=2024 형태."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name != "Field":
            continue
        for arg in [*node.args, *[kw.value for kw in node.keywords]]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int) and arg.value in _YEAR_RANGE:
                hits.append(
                    (
                        arg.lineno,
                        f"Field(... {arg.value} ...) — 연도가 상수면 해가 바뀔 때 낡는다",
                    )
                )
    return hits


def _string_date_literals(tree: ast.AST, skip_ids: set[int]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in skip_ids:
            continue
        for pattern, label in (
            (_ISO_DATE, "ISO 날짜"),
            (_COMPACT_DATE, "압축 8자리 날짜"),
        ):
            for match in pattern.findall(node.value):
                hits.append((node.lineno, f"{label} {match!r} in {node.value[:60]!r}"))
    return hits


def _allowed(relative_path: str, description: str) -> bool:
    return any(
        relative_path == path and re.search(literal_pattern, description)
        for path, literal_pattern, _reason in ALLOWLIST
    )


def _match(target: ScanTarget) -> list[Path]:
    return sorted({path for path in REPO_ROOT.glob(target.glob) if path.is_file() and "__pycache__" not in path.parts})


def _service_of(path: Path) -> str:
    """레포 루트 바로 아래 디렉터리 = 서비스 이름 (`*/app/...` 글롭의 `*` 자리)."""
    return path.relative_to(REPO_ROOT).parts[0]


def main() -> int:
    # 글롭별로 따로 잡고 따로 검사한다 — 합치고 나면 어느 축이 죽었는지 알 수 없다 (#402).
    matched: dict[str, list[Path]] = {t.label: _match(t) for t in SCAN_TARGETS}

    breakdown = " · ".join(
        f"{t.label} {len(matched[t.label])}개/{len({_service_of(p) for p in matched[t.label]})}서비스"
        for t in SCAN_TARGETS
    )
    print(f"절대 날짜 스캔 대상 — {breakdown}")

    # 글롭별 fail-closed. 합계 0건에만 걸면 원소 하나의 소실이 조용하다 (#402 실증).
    broken = False
    for target in SCAN_TARGETS:
        found = matched[target.label]
        services = {_service_of(p) for p in found}
        if len(found) < target.min_files or len(services) < target.min_services:
            print(
                f"절대 날짜 스캔 실패: 글롭 {target.glob!r}({target.label}) 가 "
                f"파일 {len(found)}개/서비스 {len(services)}개 — 하한 "
                f"{target.min_files}개/{target.min_services}개 미만이다. "
                "경로가 이동·리네임됐거나 대상이 사라졌다. "
                "정당한 삭제라면 SCAN_TARGETS 의 하한도 함께 내려라."
            )
            broken = True
    if broken:
        return 1

    files = sorted({path for found in matched.values() for path in found})
    if not files:  # 하한이 전부 0 으로 내려간 극단에서도 "0건 통과" 는 없다.
        print("절대 날짜 스캔 실패: 대상 파일 0개 — 경로 구조가 바뀌었다")
        return 1

    violations: list[str] = []
    for path in files:
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as exc:
            violations.append(f"{relative}:{exc.lineno}: 파싱 불가 (SyntaxError: {exc.msg})")
            continue
        skip_ids = _docstring_ids(tree)
        for lineno, description in [
            *_string_date_literals(tree, skip_ids),
            *_field_year_literals(tree),
        ]:
            if not _allowed(relative, description):
                violations.append(f"{relative}:{lineno}: {description}")

    if violations:
        print(f"절대 날짜 리터럴 위반 {len(violations)}건 (스캔 {len(files)}개 파일):")
        for violation in violations:
            print(f"  - {violation}")
        print("낡을 값은 조회 시점 상대 계산으로 바꾼다 (선례: #268 days_ago, #228 now_kst 기반 상한).")
        print("안 움직이는 과거 사실이면 이 스크립트의 ALLOWLIST 에 사유와 함께 등록한다.")
        return 1
    # 라벨을 손으로 쓰지 않는다 — 손으로 쓴 문구는 대상이 줄어도 그대로라 읽는 사람을 속인다
    # (#402: schemas 19개가 통째로 안 읽혔는데 출력은 여전히 "(clients·schemas)" 였다).
    print(f"절대 날짜 리터럴 없음 — {len(files)}개 파일 스캔 ({breakdown}), 위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
