"""기동 시 DB 의 alembic 리비전과 코드의 head 를 대조한다 — 어긋나면 기동을 멈춘다 (#311).

## 왜 여기인가

`alembic upgrade head` 를 부르는 자리는 `process-compose.yaml` 의 `db-migrate` 하나뿐이고,
그것에 `depends_on` 이 걸린 것은 그 파일로 띄운 `backend` 뿐이다. 루트 CLAUDE.md 가 안내하는
기동법(`cd <backend>/app && uvicorn main:app --reload`)이나 포트를 손으로 주입해 띄우는 경로는
어떤 검사도 안 태운다 — 그래서 코드가 `0018` 인데 DB 가 `0015` 인 채로 앱이 조용히 떴고,
백테스트의 읽기·쓰기만 `column "session_scope" does not exist` 로 죽었다. 목록은 「succeeded
130건」을 200 으로 내주면서 그중 하나를 열면 500 이라, 사용자는 데이터가 깨진 것인지 앱이
깨진 것인지 가를 수 없었다.

기동 스크립트가 아니라 **앱 안**에 두는 이유가 그것이다. 어떤 경로로 띄우든 이 검사를 지난다.

## 판정

- DB 리비전 == 코드 head → 통과.
- DB 리비전이 코드의 리비전 그래프 **안**에 있고 head 가 아니다 → DB 가 뒤처졌다. 최신 코드가
  기대하는 컬럼이 없다 (#311 의 증상).
- DB 리비전을 코드가 모른다 → 체크아웃이 DB 보다 뒤처졌다. 이 코드가 어떤 스키마 위에 서 있는지
  알 수 없으므로 역시 막는다.
- 리비전을 못 읽는다(테이블 없음·DB 불가·행이 여럿) → 통과가 아니라 실패다 (fail-closed).

`ALLOW_SCHEMA_DRIFT=true` 는 「알고도 띄운다」(읽기 전용 조사)를 위한 탈출구다 — 기본은 막고,
켜도 판정 결과를 ERROR 로 남긴다.
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

from alembic.script import ScriptDirectory
from core.config import settings
from core.logger import logger
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

# app/core/schema_version.py → <서비스>/alembic. 컨테이너 이미지도 같은 배치다
# (Dockerfile 이 app 과 alembic 을 나란히 복사한다 — 이 배치가 깨지면 여기가 fail-closed 로 막는다).
ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SchemaVersionError(RuntimeError):
    """DB 스키마 판을 코드 head 와 맞출 수 없다."""


def version_table_name(alembic_dir: Path = ALEMBIC_DIR) -> str:
    """버전 테이블 이름. SoT 는 alembic.ini — 한 DB 를 여러 서비스가 공유하므로 이름이 서비스마다 다르다(#166)."""
    ini = alembic_dir / "alembic.ini"
    if not ini.is_file():
        raise SchemaVersionError(f"alembic 설정을 찾지 못했다: {ini}")
    # script_location 의 `%(here)s` 는 alembic 이 해석한다 — 여기서 보간하면 읽기 자체가 실패한다.
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ini, encoding="utf-8")
    name = parser.get("alembic", "version_table", fallback="alembic_version")
    if not _IDENTIFIER.match(name):
        raise SchemaVersionError(f"alembic.ini 의 version_table 이 식별자가 아니다: {name!r}")
    return name


def code_head_revision(alembic_dir: Path = ALEMBIC_DIR) -> tuple[str, set[str]]:
    """(코드 head 리비전, 코드가 아는 리비전 전부)."""
    versions = alembic_dir / "versions"
    if not versions.is_dir():
        raise SchemaVersionError(f"alembic 리비전 디렉터리가 없다: {versions}")
    script = ScriptDirectory(str(alembic_dir))
    heads = script.get_heads()
    if len(heads) != 1:
        raise SchemaVersionError(
            f"코드의 alembic head 가 {len(heads)}개다 ({', '.join(heads) or '없음'}) — "
            "어느 판을 기대해야 하는지 정할 수 없다"
        )
    return heads[0], {revision.revision for revision in script.walk_revisions()}


def db_revision(engine: Engine, table: str) -> str | None:
    """DB 에 적용된 리비전. 한 번도 적용된 적이 없으면 None, 읽지 못하면 SchemaVersionError."""
    try:
        with engine.connect() as connection:
            # 테이블 이름은 바인딩 대상이 아니다 — alembic.ini 에서 와 식별자 검증(_IDENTIFIER)을 거친다.
            rows = connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all()
    except SQLAlchemyError as exc:
        raise SchemaVersionError(
            f"DB 의 {table} 을 읽지 못했다 ({type(exc).__name__}) — 마이그레이션이 한 번도 적용되지 않았거나 "
            "DB 에 닿지 못한다"
        ) from exc
    if not rows:
        return None
    if len(rows) > 1:
        raise SchemaVersionError(f"DB 의 {table} 에 리비전이 {len(rows)}개다 ({', '.join(sorted(rows))})")
    return rows[0]


def drift_reason(code_head: str, known: set[str], db_current: str | None) -> str | None:
    """어긋난 사유 한 줄. 일치하면 None."""
    if db_current is None:
        return "DB 에 적용된 리비전이 없다 — 마이그레이션이 한 번도 적용되지 않았다"
    if db_current == code_head:
        return None
    if db_current in known:
        return f"DB 스키마가 코드보다 뒤처졌다 — DB `{db_current}` / 코드 head `{code_head}`"
    return (
        f"DB 에 코드가 모르는 리비전이 있다 — DB `{db_current}` / 코드 head `{code_head}` (체크아웃이 DB 보다 뒤처졌다)"
    )


def how_to_fix(alembic_dir: Path = ALEMBIC_DIR) -> str:
    return (
        f"적용: (cd {alembic_dir} && APP_ENV={settings.APP_ENV} uv run python -m alembic upgrade head)"
        " · 이 판 그대로 띄워야 하면 ALLOW_SCHEMA_DRIFT=true"
        " (최신 스키마를 읽는 경로 — 백테스트 등 — 는 그대로 500 이다)"
    )


def ensure_schema_matches_code(
    engine: Engine,
    *,
    alembic_dir: Path = ALEMBIC_DIR,
    allow_drift: bool | None = None,
) -> None:
    """판이 어긋나면 SchemaVersionError. `allow_drift` 가 참이면 ERROR 로그만 남기고 통과시킨다."""
    allowed = settings.ALLOW_SCHEMA_DRIFT if allow_drift is None else allow_drift
    current: str | None = None
    try:
        code_head, known = code_head_revision(alembic_dir)
        current = db_revision(engine, version_table_name(alembic_dir))
        reason = drift_reason(code_head, known, current)
    except SchemaVersionError as exc:
        reason = str(exc)

    if reason is None:
        logger.info(f"DB 스키마 판 확인 — alembic 리비전 {current} (코드 head 와 일치)")
        return

    message = f"DB 스키마 판이 코드와 다르다: {reason}. {how_to_fix(alembic_dir)}"
    if allowed:
        logger.error(f"ALLOW_SCHEMA_DRIFT=true — 판 불일치를 알고도 기동한다. {message}")
        return
    raise SchemaVersionError(message)
