"""`frontend.tn_user` 가 있는지 한 글자로 답한다 — `db-migrate` 가 순서를 가르는 데 쓴다 (#359).

## 왜 필요한가

`process-compose.yaml` 의 `db-migrate` 는 **기존 DB 에서만** `prisma db push` 앞에 alembic 을
먼저 돌려야 한다 — 리비전 `0019` 가 `frontend` 의 naive 값을 행 기원별 `USING` 으로 옮기는데,
push 가 먼저 돌면 같은 컬럼을 `USING` 없이 바꿔 뜻을 뭉개기 때문이다. 반대로 **신규 DB** 에서는
`frontend` 스키마 자체가 없어 `0005`·`0007` 의 fail-closed 가드(#333)가 죽으므로 먼저 돌릴 수
없다.

두 경우를 가르는 판정이 이 스크립트다. `psql` 에 기대지 않는다 — 로컬 스택(pgserver)에는
클라이언트 바이너리가 PATH 에 없다. 접속 정보는 통합 앱과 **같은 자리**(`core.config.settings`
← `app/.env.$APP_ENV`)에서 읽으므로 db-migrate 가 별도 env 를 들고 있을 필요가 없다.

    cd backend-service/app && APP_ENV=development uv run python ../scripts/frontend_schema_present.py
    # stdout: "t" (있다) 또는 "f" (없다)

DB 에 닿지 못하면 통과가 아니라 **실패**다(exit 2) — "못 봤다"를 "없다"로 읽으면 기존 DB 를
신규 DB 취급해 순서를 거꾸로 태운다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 스크립트를 경로로 실행하면 sys.path 에 들어가는 것은 `scripts/` 다 — 앱 모듈을 직접 넣는다
# (backend-service 의 다른 검증 스크립트와 같은 관례). cwd 는 `app` 이어야 한다 — `core.config`
# 가 `.env.$APP_ENV` 를 cwd 기준으로 읽는다(루트 CLAUDE.md).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import sqlalchemy as sa  # noqa: E402
from core.config import settings  # noqa: E402
from utils.common.database_utils import get_sql_db_url  # noqa: E402


def main() -> int:
    url = get_sql_db_url(
        driver=settings.BACKEND_SQL_DB_DRIVER,
        odbc_driver=settings.BACKEND_SQL_DB_ODBC_DRIVER,
        host=settings.BACKEND_SQL_DB_HOST,
        port=settings.BACKEND_SQL_DB_PORT,
        dbname=settings.BACKEND_SQL_DB_NAME,
        user=settings.BACKEND_SQL_DB_USER,
        password=settings.BACKEND_SQL_DB_PASSWORD,
    )
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            present = connection.execute(sa.text("SELECT to_regclass('frontend.tn_user') IS NOT NULL")).scalar()
    except sa.exc.SQLAlchemyError as exc:
        print(f"frontend 스키마 유무를 확인하지 못했다 ({type(exc).__name__}) — DB 에 닿지 못한다", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    print("t" if present else "f")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
