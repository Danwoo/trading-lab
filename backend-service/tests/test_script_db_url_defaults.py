"""#386 — 스크립트의 기본 DB URL 이 psycopg 파서를 통과하는지 (기본값 그대로 돌아가는가).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_script_db_url_defaults.py

배경: `kst_timestamp_correction.py` 의 기본 URL 이 `?options=-csearch_path=frontend` 였다. 쿼리
파라미터 값 안의 날것 `=` 를 libpq URI 파서가 거절해(`extra key/value separator "="`) `--db-url`
없이 돌리면 첫 명령부터 죽었다 — 되돌리기 어려운 마이그레이션 직전에 쓰라고 만든 감사 도구가
그 자리에서 안 도는 상태였다. 값 안의 `=` 는 `%3D` 로 인코딩해야 한다.

검사: 레포의 `*/scripts/*.py` + 루트 `scripts/*.py` 를 AST 로 훑어 `postgres://`·`postgresql://`
로 **시작하는 문자열 리터럴**(상수 기본값·`os.getenv(..., "…")` 기본값)을 모으고, 하나하나
`psycopg.conninfo.conninfo_to_dict()` 로 파싱한다. DB 접속은 하지 않는다 — 파싱만으로 이 결함이
드러나기 때문이다. SQLAlchemy 방언 URL(`postgresql+psycopg://`)은 psycopg 에 그대로 넘기는
값이 아니므로 건너뛰고 그 수를 함께 보고한다.

**fail-closed**: 수집한 URL 이 0건이면 실패한다 — 글롭·이름 규칙이 어긋나 아무것도 안 본 것을
"위반 없음"으로 읽지 않기 위해서다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import psycopg

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PSYCOPG_SCHEMES = ("postgresql://", "postgres://")
_SQLALCHEMY_SCHEME_MARK = "postgresql+"
# 수집 대상 스크립트가 사라지거나 글롭이 어긋나면 조용히 초록이 되지 않도록 하는 하한
# (현재 3건: kst_timestamp_correction · verify_no_orphan_personal_workspaces ·
#  verify_workspace_member_default_unique).
_EXPECTED_MIN_URLS = 3
# `?options=-csearch_path=frontend` — 고치기 전 형태. 파서가 이것을 실제로 거절하는지 함께
# 확인해, 위 검사가 "무엇이든 통과시키는" 헛그물이 아님을 증명한다.
_KNOWN_BAD_URL = "postgresql://u:p@localhost:5432/db?options=-csearch_path=frontend"


def _script_files() -> list[Path]:
    return sorted({*_REPO_ROOT.glob("*/scripts/*.py"), *(_REPO_ROOT / "scripts").glob("*.py")})


def _collect_db_urls() -> tuple[list[tuple[Path, str]], int]:
    """(파일, URL 리터럴) 목록과 건너뛴 SQLAlchemy 방언 URL 수."""
    found: list[tuple[Path, str]] = []
    dialect_skipped = 0
    for path in _script_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            value = node.value
            if value.startswith(_SQLALCHEMY_SCHEME_MARK):
                dialect_skipped += 1
                continue
            if value.startswith(_PSYCOPG_SCHEMES):
                found.append((path, value))
    return found, dialect_skipped


def test_script_db_url_defaults_parse() -> str:
    urls, dialect_skipped = _collect_db_urls()
    assert len(urls) >= _EXPECTED_MIN_URLS, (
        f"스크립트에서 수집한 psycopg DB URL {len(urls)}건 — 기대 하한 {_EXPECTED_MIN_URLS}건 "
        "미만이다 (글롭·이름 규칙이 어긋나 검사가 헛돌고 있다)"
    )
    for path, url in urls:
        relative = path.relative_to(_REPO_ROOT)
        try:
            psycopg.conninfo.conninfo_to_dict(url)
        except psycopg.ProgrammingError as exc:  # noqa: PERF203 — 어느 URL 인지 알려야 한다
            raise AssertionError(
                f"{relative}: 기본 DB URL 이 psycopg 파서에서 거절됐다 ({exc}). 쿼리 파라미터 "
                "값 안의 `=` 는 %3D 로 인코딩할 것"
            ) from None
    print(f"  검사한 DB URL {len(urls)}건 (SQLAlchemy 방언 {dialect_skipped}건 제외)")
    return "test_script_db_url_defaults_parse"


def test_parser_rejects_unencoded_equals() -> str:
    """그물이 헛돌지 않는지 — 고치기 전 형태는 실제로 거절돼야 한다."""
    try:
        psycopg.conninfo.conninfo_to_dict(_KNOWN_BAD_URL)
    except psycopg.ProgrammingError:
        return "test_parser_rejects_unencoded_equals"
    raise AssertionError("인코딩 안 된 `=` 를 가진 URL 이 파서를 통과했다 — 이 검사는 아무것도 못 잡는다")


def test_kst_correction_default_targets_frontend_schema() -> str:
    """감사 도구의 기본 URL 이 파싱될 뿐 아니라 frontend 스키마를 실제로 겨냥하는지."""
    path = _REPO_ROOT / "backend-service" / "scripts" / "kst_timestamp_correction.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    default = next(
        (
            node.value.value
            if isinstance(node.value, ast.Constant)
            else "".join(
                part.value
                for part in ast.walk(node.value)
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "DB_URL_DEFAULT" for t in node.targets)
        ),
        None,
    )
    assert default, "kst_timestamp_correction.py 에서 DB_URL_DEFAULT 를 못 찾았다"
    options = psycopg.conninfo.conninfo_to_dict(default).get("options", "")
    assert "search_path=frontend" in options, (
        f"DB_URL_DEFAULT 의 options 가 frontend 스키마를 겨냥하지 않는다: {options!r}"
    )
    return "test_kst_correction_default_targets_frontend_schema"


def _main() -> int:
    tests = [
        test_script_db_url_defaults_parse,
        test_parser_rejects_unencoded_equals,
        test_kst_correction_default_targets_frontend_schema,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
