"""Milvus 벡터DB 연결 (외부타입 MilvusClient) — 검색 전용. 컬렉션 생성·적재는 인덱싱 파이프라인 소유.

fail-soft: 연결 실패 시 raise 하지 않고 None 을 돌려 기동을 막지 않는다 (USE_REAL_API=false 의 MOCK 경로는
Milvus 없이 동작해야 한다). 실제 검색(search_*)은 USE_REAL_API=true 경로에서만 호출되며, 그때 None 이면
service 가 인프라 장애로 보고 MOCK 으로 폴백한다.
"""

from core.logger import logger
from pymilvus import MilvusClient


def get_milvus_client(config) -> MilvusClient | None:
    try:
        return MilvusClient(
            uri=config.MILVUS_DB_HOST,
            token=config.MILVUS_DB_TOKEN,
            db_name=config.MILVUS_DB_NAME,
        )
    except Exception as e:
        logger.warning("Milvus 벡터DB 연결 실패 — MOCK 폴백 가능 (USE_REAL_API=false 면 정상): %s", e)
        return None
