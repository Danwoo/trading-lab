"""#234 — SQL 바인딩 파라미터가 예외 문자열(→ 트레이스백)로 새지 않는지 검증.

배경: core/exception_handler.py 는 5xx·연결 오류·미분류 예외를 exc_info=True 로 찍는다. 트레이스백
마지막 줄이 SQLAlchemy StatementError.__str__ 이라 거기 `[parameters: {...}]` 로 삽입하려던 행 값이
통째로 실렸다 (#216 이 막은 무결성 오류 DETAIL 과 같은 값의 다른 경로). 처방은 엔진의
hide_parameters=True — 그래서 검증 지점은 핸들러가 아니라 엔진 팩토리다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_sql_parameter_hiding.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

CI 배선: .github/workflows/ci.yml 의 `test: repo` 잡(경로 필터 없는 전수
스캔) + ci.yml 의 `test: backend` 스위트(tests/ 글롭). 테스트만 있고 잡이 없으면
그물은 초록으로 죽는다 — 이 파일을 옮기거나 이름을 바꾸면 그 잡도 같이 고쳐야 한다.

외부 DB 없이 돈다 — 행동 검증은 sqlite in-memory 로, 서버 DB 분기는 AST 로 확인한다.
AST 검사는 자기 서비스 사본이 아니라 **레포 안 엔진 생성 호출 전수**를 본다: 사본이 byte-identical
이라는 전제(강제하는 CI 검사가 없다)에 기대면 남의 사본에서 플래그가 지워져도 초록이고, 동기
database_utils 밖의 엔진(alembic·doc-search AsyncEngine)은 아예 보이지도 않는다.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# Settings 가 env_file(.env.{APP_ENV})을 읽는다 — 존재하지 않는 이름을 줘 파일 간섭을 끊고,
# 필수 필드는 env 로 채운다 (여기서 만드는 엔진은 sqlite 라 이 값들로 접속하지 않는다).
os.environ["APP_ENV"] = "sql-param-hiding-test"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("BACKEND_SQL_DB_DRIVER", "sqlite")
os.environ.setdefault("BACKEND_SQL_DB_HOST", "")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "5432")
os.environ.setdefault("BACKEND_SQL_DB_NAME", ":memory:")
os.environ.setdefault("BACKEND_SQL_DB_USER", "")
os.environ.setdefault("BACKEND_SQL_DB_PASSWORD", "")
# file 모듈 흡수(#244)로 Settings 의 필수 필드가 늘었다 — import 사슬이 core.config 까지 닿으므로
# 여기서도 채워야 한다 (SFTP 에 접속하지는 않는다. tests/test_ingest_status_boundary.py 와 같은 방식).
os.environ.setdefault("SFTP_HOST", "localhost")
os.environ.setdefault("SFTP_PORT", "22")
os.environ.setdefault("SFTP_USERNAME", "test")
os.environ.setdefault("SFTP_PASSWORD", "test")

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import StatementError  # noqa: E402
from utils.common.database_utils import create_sql_engine_from_settings  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
PII = "110-234-567890"  # 예외 문자열 어디에도 나오면 안 되는 값

# 엔진을 만드는 호출 전부. 하나라도 플래그가 빠지면 그 엔진이 낸 예외로 값이 샌다 —
# 동기(create_engine)·비동기(create_async_engine)·alembic(engine_from_config) 셋이 현재 쓰이는 형태다.
ENGINE_FACTORY_CALLS = frozenset({"create_engine", "create_async_engine", "engine_from_config"})
# 가상환경·VCS·캐시는 우리 소스가 아니다. 숨김 디렉터리는 통째로 제외한다(.venv·.git·.docs …).
_SKIP_DIRS = frozenset({"node_modules", "__pycache__", "site-packages"})


def _memory_engine():
    return create_sql_engine_from_settings(
        db_name_log="TEST",
        driver="sqlite",
        host="",
        port=0,
        dbname=":memory:",
        user="",
        password="",
    )


def test_engine_sets_hide_parameters() -> str:
    """팩토리가 만든 엔진에 hide_parameters 가 켜져 있다 (설정 누락 시 전 경로가 다시 샌다)."""
    engine = _memory_engine()
    try:
        assert engine.hide_parameters is True, "엔진에 hide_parameters=True 가 없음"
    finally:
        engine.dispose()
    return "test_engine_sets_hide_parameters"


def test_statement_error_omits_parameter_values() -> str:
    """실제 DB 오류의 str(exc) 에 바인딩 값이 없고, 진단(문장·드라이버 메시지)은 남는다."""
    engine = _memory_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE probe (code TEXT PRIMARY KEY, account_no TEXT NOT NULL)"))
            conn.execute(
                text("INSERT INTO probe (code, account_no) VALUES (:c, :a)"),
                {"c": "AAA", "a": "110-000-000001"},
            )
            try:
                conn.execute(
                    text("INSERT INTO probe (code, account_no) VALUES (:c, :a)"),
                    {"c": "AAA", "a": PII},  # PK 중복
                )
            except StatementError as exc:
                message = str(exc)
            else:
                raise AssertionError("PK 중복인데 예외가 없음 — 시나리오가 성립하지 않았다")
    finally:
        engine.dispose()

    assert PII not in message, f"바인딩 값이 예외 문자열에 남아 있음: {message}"
    assert "[parameters:" not in message, f"`[parameters: ...]` 블록이 남아 있음: {message}"
    # 진단이 통째로 사라지면 처방이 과했다는 뜻 — 아래 둘은 반드시 남아야 한다.
    assert "[SQL:" in message, f"실패한 문장이 사라짐 (진단 불가): {message}"
    assert "UNIQUE constraint failed" in message, f"드라이버 메시지가 사라짐 (진단 불가): {message}"
    return "test_statement_error_omits_parameter_values"


def _iter_python_sources(root: Path):
    """레포 안 우리 파이썬 소스 (가상환경·VCS·캐시 제외)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _callee_name(func: ast.expr) -> str | None:
    """`create_engine(...)` 과 `sa.create_engine(...)` 둘 다 이름을 뽑는다."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_all_engine_factories_hide_parameters() -> str:
    """레포 안 모든 엔진 생성 호출에 hide_parameters=True 가 붙어 있다 (AST 전수).

    sqlite 분기만 행동 검증되므로 실제 배포가 쓰는 비-sqlite 분기는 정적으로 못 박는다. 대상을
    자기 서비스 사본으로 좁히지 않는 이유: (ㄱ) database_utils.py 사본 동일성을 강제하는 검사가
    없어 남의 사본만 지워질 수 있고, (ㄴ) alembic(engine_from_config)·doc-search(AsyncEngine)처럼
    사본 밖에 사는 엔진이 실재한다 — 실제로 alembic 이 그렇게 1차 처방에서 빠졌다.

    fail-closed: 소스를 못 찾거나 엔진 호출이 0건이면 "위반 없음"이 아니라 스캔이 깨진 것이다.
    """
    sources = list(_iter_python_sources(_REPO_ROOT))
    assert sources, f"파이썬 소스가 0건 — 스캔 경로가 깨졌다: {_REPO_ROOT}"

    calls: list[tuple[Path, int, str]] = []
    missing: list[str] = []
    unparsed: list[str] = []
    for path in sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:  # 조용히 건너뛰면 그 파일은 무검사가 된다
            unparsed.append(f"{path.relative_to(_REPO_ROOT)}: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _callee_name(node.func)
            if callee not in ENGINE_FACTORY_CALLS:
                continue
            calls.append((path, node.lineno, callee))
            # 리터럴 kwarg 만 인정한다 — `**opts` 로 넘기면 여기서는 못 읽으므로 누락으로 잡힌다.
            # 오탐 방향이지만 시끄럽게 실패하는 쪽이라, 조용히 통과시키는 것보다 낫다.
            flag = next((kw.value for kw in node.keywords if kw.arg == "hide_parameters"), None)
            if not (isinstance(flag, ast.Constant) and flag.value is True):
                missing.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}: {callee} 에 hide_parameters=True 없음")

    assert not unparsed, "파싱 실패한 소스가 있어 전수 검사가 성립하지 않는다:\n  " + "\n  ".join(unparsed)
    assert calls, f"엔진 생성 호출이 0건 — 검사 대상이 사라졌다 (소스 {len(sources)}개 스캔)"
    assert not missing, "플래그 누락:\n  " + "\n  ".join(missing)

    # 무엇을 몇 건 검사했는지 남긴다 — 초록이 "위반 없음"인지 "아무것도 안 봤음"인지 구분되게.
    print(f"  엔진 생성 호출 {len(calls)}건 (소스 {len(sources)}개 스캔) — 전부 hide_parameters=True:")
    for path, lineno, func in calls:
        print(f"    {path.relative_to(_REPO_ROOT)}:{lineno} {func}")
    return f"test_all_engine_factories_hide_parameters (소스 {len(sources)}개 / 엔진 호출 {len(calls)}건)"


def _main() -> int:
    tests = [
        test_engine_sets_hide_parameters,
        test_statement_error_omits_parameter_values,
        test_all_engine_factories_hide_parameters,
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
