#!/usr/bin/env python3
"""화면에 나가는 「왜 안 되나」 사유가 내부 어휘를 담지 않는지 확인한다 (#319).

## 왜 이 그물이 있나

시세 패널의 「막혀 있는 것」 사유 12가지 중 셋이 개발자 말로 쓰여 있었다 — 실측:

    미국 종목 마스터의 정본 소스는 SEC 입니다 (MD-AD-17 — 시장마다 정본 소스 하나)
    prices 응답에 등락·등락률·거래량이 없어(사양) 시세 계약을 채울 수 없습니다
    호가 어댑터를 아직 붙이지 않았습니다

`MD-AD-17` 은 내부 설계 문서의 결정 번호이고, 「어댑터」는 `providers/` 의 구현 단위 이름이며,
`prices` 는 상류 엔드포인트 이름이다. 이 자리는 **사용자가 막혔을 때 읽는 문장**이라 모르는 말이
나오면 그 자리가 끝난다. 같은 부류(영문 예외 원문이 화면에 나오는 것)를 이 레포는 이미 두 번
고쳤다(#251·#287) — 문구는 사람이 다시 쓰기 쉬운 자리라 기계가 지켜야 재발이 잡힌다.

## 무엇을 확인하나

두 축을 따로 센다. 어느 한 축이 0건이면 실패한다(fail-closed).

1. **실제 사유** — 등록된 소스 전부를 키 있는/없는 두 상태로 만들어 `capabilities()` 가 내는
   사유를 모으고, 소스 호출 실패 문구(`providers/failure.py`)도 함께 모은다. 어댑터가 새로
   들어와도 목록을 손보지 않아도 검사 대상이 된다.
2. **사유가 태어나는 자리의 문자열** — 조건 분기에 가려 위 축에 안 잡히는 문장까지 본다.
   `ast` 로 파싱해 네 자리만 고른다: `reason=` 인자 · `*_REASON`/`*_HINT`/`*_NOTE` 상수 ·
   이름에 `reason` 이 든 함수의 `return` · 화면까지 흐르는 예외(`*Error`/`*Invalid`/`*Missing`)
   의 생성자 인자. **주석·docstring 은 안 본다** — 근거(설계 번호)를 적는 자리는 오히려 거기다.

    cd backend-service && APP_ENV=development uv run python scripts/verify_screen_reason_wording.py
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

# 어댑터를 실제로 import 하려면 `core.config` 가 뜬다 — `.env.development` 는 로컬에만 있으므로
# 러너에서도 같은 결과가 나오도록 최소값을 채운다 (다른 verify_* 스크립트와 같은 관례).
os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
for _key in (
    "BACKEND_SQL_DB_DRIVER",
    "BACKEND_SQL_DB_HOST",
    "BACKEND_SQL_DB_NAME",
    "BACKEND_SQL_DB_USER",
    "BACKEND_SQL_DB_PASSWORD",
):
    os.environ.setdefault(_key, "x")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "1433")
for _key in ("SFTP_HOST", "SFTP_USERNAME", "SFTP_PASSWORD"):
    os.environ.setdefault(_key, "x")
os.environ.setdefault("SFTP_PORT", "22")

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
sys.path.insert(0, str(APP))

FAILURES: list[str] = []
SEEN: set[tuple[str, str]] = set()

#: 화면 문장에 들어오면 안 되는 것. (정규식, 사람이 읽는 이름, 대신 무엇을 하라)
BANNED: list[tuple[str, str, str]] = [
    (r"\b(?:MD|M2)-AD-\d+", "설계 문서 결정 번호", "번호는 코드 주석에 두고 문장은 뜻으로 풀어 쓰세요"),
    (r"어댑터|프로바이더|리포지토리", "구현 단위 이름", "사용자는 코드 구조를 모릅니다 — 소스 이름으로 말하세요"),
    (r"(?i)\b(?:adapter|provider|protocol|endpoint)\b", "구현 어휘(영문)", "한국어 사용자 문장으로 쓰세요"),
    (
        r"\b(?:prices|candles|quotes|tickers|companyfacts|stocks/all)\b",
        "상류 엔드포인트 이름",
        "무엇이 없어서 못 하는지를 데이터 이름으로 쓰세요",
    ),
    (r"시세 계약|정규화 모델|Normalized", "내부 계약 이름", "화면이 무엇을 못 채우는지로 쓰세요"),
]

#: 사유 문자열이 태어나는 자리. 여기 없는 파일이 사유를 만들기 시작하면 이 목록에 더한다.
SOURCE_FILES = [
    APP / "providers" / "base.py",
    APP / "providers" / "failure.py",
    APP / "services" / "capability" / "capability_service.py",
    APP / "services" / "bar" / "bar_service.py",
    *sorted(APP.glob("providers/*/adapter.py")),
]


def scan(text: str, where: str) -> None:
    """같은 문장이 여러 자리에서 나오면(시장마다 한 줄) 첫 자리 하나만 적는다 — 출력이 읽히게."""
    for pattern, label, todo in BANNED:
        hit = re.search(pattern, text)
        if hit:
            key = (label, text)
            if key in SEEN:
                continue
            SEEN.add(key)
            FAILURES.append(f"{where}: {label} '{hit.group(0)}' 이(가) 화면 문장에 있습니다 — {todo}\n    문장: {text}")


def collect_live_reasons() -> list[tuple[str, str]]:
    """등록된 소스 전부의 `capabilities()` 사유 + 소스 실패 문구."""
    import httpx
    from providers import get_provider, list_sources
    from providers.failure import describe_provider_failure

    out: list[tuple[str, str]] = []
    for source in sorted(list_sources()):
        # 키 유무로 사유가 갈리므로 두 상태를 다 태운다.
        for api_key in (None, "DUMMYID:DUMMYSECRET"):
            provider = get_provider(source, api_key)
            for capability in provider.capabilities():
                if capability.reason:
                    out.append((f"{source}/{capability.market}/{capability.data_kind}", capability.reason))

    request = httpx.Request("GET", "https://example.test/x")
    failures: list[BaseException] = [
        httpx.HTTPStatusError("boom", request=request, response=httpx.Response(status, request=request))
        for status in (400, 401, 403, 404, 429, 500, 302)
    ]
    failures += [
        httpx.TimeoutException("boom", request=request),
        httpx.ConnectError("boom", request=request),
        httpx.DecodingError("boom", request=request),
        RuntimeError("boom"),
    ]
    for exc in failures:
        out.append((f"failure/{type(exc).__name__}", describe_provider_failure(exc, "toss")))
    return out


#: 이름이 이렇게 끝나는 예외는 그 메시지가 API 응답 `detail`·적재 실행 기록으로 화면까지 간다.
SCREEN_EXCEPTION = re.compile(r"(?:Error|Invalid|Missing)$")
#: 사유 문구를 담는 상수 이름.
REASON_NAME = re.compile(r"(?:REASON|HINT|NOTE)$")


def _strings(node: ast.AST) -> list[tuple[int, str]]:
    """이 표현식 안의 문자열 조각 — f-string 의 고정 부분도 포함한다."""
    out: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append((child.lineno, child.value))
    return out


def _reason_expressions(tree: ast.AST) -> list[ast.AST]:
    """사유 문구가 태어나는 표현식만 고른다."""
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(REASON_NAME.search(name) for name in names):
                found.append(node.value)
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "reason":
                    found.append(kw.value)
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if SCREEN_EXCEPTION.search(name):
                found.extend(node.args)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "reason" in node.name:
            found.extend(child.value for child in ast.walk(node) if isinstance(child, ast.Return) and child.value)
    return found


def collect_literals() -> list[tuple[str, str]]:
    """사유가 태어나는 자리의 문자열. 주석·docstring 은 보지 않는다."""
    out: list[tuple[str, str]] = []
    for path in SOURCE_FILES:
        if not path.is_file():
            FAILURES.append(f"검사 대상 파일이 없습니다: {path} — 목록이 낡았습니다")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for expression in _reason_expressions(tree):
            for lineno, text in _strings(expression):
                out.append((f"{path.relative_to(BACKEND)}:{lineno}", text))
    return out


def main() -> int:
    live = collect_live_reasons()
    literals = collect_literals()

    for where, text in live:
        scan(text, where)
    for where, text in literals:
        scan(text, where)

    print(f"검사한 실제 사유 {len(live)}건 · 사유 파일 {len(SOURCE_FILES)}개에서 사유 문구 {len(literals)}건")

    if len(live) < 40:
        print(
            f"::error::실제 사유를 {len(live)}건만 모았습니다 — 소스 등록이 죽었을 수 있습니다, fail-closed 종료",
            file=sys.stderr,
        )
        return 1
    if len(literals) < 30:
        print(
            f"::error::사유가 태어나는 자리의 문자열을 {len(literals)}건만 모았습니다 — 목록이 비었을 수 있습니다, fail-closed 종료",
            file=sys.stderr,
        )
        return 1

    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        print(f"::error::화면 사유 {len(FAILURES)}건이 내부 어휘를 담고 있습니다 (#319)", file=sys.stderr)
        return 1

    print("판정: 화면에 나가는 사유가 설계 번호·구현 단위 이름·상류 엔드포인트 이름을 담지 않는다 (#319)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
