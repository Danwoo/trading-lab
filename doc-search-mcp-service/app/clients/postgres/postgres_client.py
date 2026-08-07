"""워크스페이스 문서 벡터 스토어(pgvector) 연결 — 외부타입 SQLAlchemy AsyncEngine 을 만드는 get_* 팩토리.

doc-search 는 원래 async(httpx) 서비스라 async pg 드라이버(asyncpg)를 쓴다 — backend-service 의 동기 Engine
규약(anti-pattern 12)은 업무 DB 경로 전용이라 여기 적용하지 않는다(design-160-pgvector-delta §1).

fail-soft: host 미설정이면 None 을 돌려 기동을 막지 않는다 — WORKSPACE_REAL_API=false 의 MOCK 경로는 pg 없이
동작해야 한다. 실제 색인/검색은 host 설정 + WORKSPACE_REAL_API=true 경로에서만 일어난다(#190 토글 분리).
"""

from core.logger import logger
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def get_workspace_engine(config) -> AsyncEngine | None:
    if not config.DOC_VECTOR_DB_HOST:
        return None
    try:
        url = URL.create(
            "postgresql+asyncpg",
            username=config.DOC_VECTOR_DB_USER,
            password=config.DOC_VECTOR_DB_PASSWORD,
            host=config.DOC_VECTOR_DB_HOST,
            port=config.DOC_VECTOR_DB_PORT,
            database=config.DOC_VECTOR_DB_NAME,
        )
        # 연결은 lazy(첫 쿼리에서 수립). pool_pre_ping 으로 끊긴 커넥션 자동 폐기.
        # hide_parameters=True — 예외 문자열에 바인딩 파라미터가 실리지 않게 (#234, database_utils 와 동일 정책).
        return create_async_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True, hide_parameters=True)
    except Exception as e:
        logger.warning("워크스페이스 pg 엔진 생성 실패 — MOCK 폴백 가능 (WORKSPACE_REAL_API=false 면 정상): %s", e)
        return None
