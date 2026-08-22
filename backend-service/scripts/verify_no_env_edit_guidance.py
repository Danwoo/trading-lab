"""화면에 나가는 사유가 `.env` 편집을 시키지 않는지 검증 (#317, fail-closed).

키를 넣는 자리는 **설정 화면**(`/settings` — `DataKeyService.save_key`)이다. 그런데 사유 문구는
그 화면이 생기기 전에 쓰여, 코딩을 모르는 사용자에게 파일을 열라고 말하고 있었다(실측: 시세
패널의 「키를 넣으면 열리는 것」 15건이 전부 `.env 에 데이터 소스 키를 채우세요` 였다). 화면이
대신해 주는 일을 파일 편집으로 지시하면, 제품은 이미 만들어 둔 문 앞에 벽을 세운다.

**규칙**: `app/` 의 문자열 리터럴이 `.env` 를 지목하면서 동시에 **지시형 어미**(채우세요·
넣으세요·적으세요·수정하세요·편집하세요)를 쓰면 위반이다. 사실 서술(「… 이 아직 비어 있습니다」)
은 대상이 아니다 — 이 그물이 막는 것은 「어디를 어떻게 고쳐라」이지 「무엇이 없다」가 아니다.

**예외는 목록에 이유와 함께 적는다** — 화면에 그 경로가 아예 없는 조작(키 삭제)만 남긴다.

**fail-closed**: 스캔한 파일이 0건이거나 파싱에 실패하면 실패한다. 검사한 개수를 항상 출력해
통과가 "위반 없음"인지 "아무것도 안 봤음"인지 구분되게 한다.

실행: `cd backend-service && python3 scripts/verify_no_env_edit_guidance.py`
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_APP_DIR = _BACKEND_DIR / "app"

#: `.env` 를 지목하면서 무엇을 하라고 시키는 모양.
_ENV_MENTION = re.compile(r"\.env\b")
_IMPERATIVE = re.compile(r"(채우|넣으|적으|수정하|편집하|열어)세요")

#: 사람이 판단해 통과시킨 자리 — 화면에 그 조작 자체가 없는 것만.
ALLOWED: dict[tuple[str, str], str] = {
    (
        "app/services/data_key/data_key_service.py",
        "지우려면",
    ): "키 삭제는 설정 화면에 없는 조작이다 — 파일이 유일한 경로라 그렇게 말하는 것이 정직하다",
}


def literal_text(node: ast.AST) -> str | None:
    """문자열 리터럴의 사람이 읽는 본문. f-string 은 자리표시자를 `{}` 로 눌러 이어 붙인다."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def excused(rel_path: str, text: str) -> bool:
    return any(rel == rel_path and marker in text for (rel, marker) in ALLOWED)


def main() -> int:
    if not _APP_DIR.is_dir():
        print(f"::error::app 디렉터리가 없습니다: {_APP_DIR} — fail-closed 종료")
        return 1

    scanned = 0
    checked_literals = 0
    violations: list[str] = []

    for path in sorted(_APP_DIR.rglob("*.py")):
        rel = path.relative_to(_BACKEND_DIR).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # 파싱 실패를 통과로 뭉개지 않는다
            print(f"::error::{rel} 를 파싱하지 못했습니다: {exc}")
            return 1
        scanned += 1
        for node in ast.walk(tree):
            text = literal_text(node)
            if text is None:
                continue
            checked_literals += 1
            if not (_ENV_MENTION.search(text) and _IMPERATIVE.search(text)):
                continue
            if excused(rel, text):
                continue
            violations.append(f"{rel}:{getattr(node, 'lineno', '?')}: {text.strip()}")

    if scanned == 0:
        print(f"::error::{_APP_DIR} 에서 파이썬 파일을 0건 수집했습니다 — fail-closed 종료")
        return 1

    print(f"파이썬 파일 {scanned}개 · 문자열 리터럴 {checked_literals}개 검사 (예외 {len(ALLOWED)}건)")

    if violations:
        print(f"::error::`.env` 편집을 지시하는 문구 {len(violations)}건")
        for violation in violations:
            print(f"::error::  {violation}")
        print("::error::키를 넣는 자리는 설정 화면입니다 — 사유는 무엇이 없는지까지만 말하세요.")
        return 1

    print("`.env` 편집 지시 0건 — 화면이 대신하는 일을 파일 편집으로 시키지 않는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
