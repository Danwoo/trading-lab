from clients.bm25.bm25_client import Bm25Client
from clients.embedding.embedding_client import EmbeddingClient
from clients.milvus.milvus_client import get_milvus_client
from clients.parser.parser import get_parser
from clients.postgres.postgres_client import get_workspace_engine
from clients.redis.redis_client import get_redis_client
from clients.reranker.reranker_client import RerankerClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.vector_search.vector_search_milvus_repository import VectorSearchMilvusRepository
from repositories.workspace.workspace_chunk_repository import WorkspaceChunkRepository
from services.vector_search.vector_search_service import VectorSearchService
from services.workspace.workspace_service import WorkspaceService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부 연결 — Milvus/Redis 는 외부타입 get_* 팩토리, 임베딩/리랭커/BM25 는 우리 클래스)
    milvus_client = providers.Singleton(get_milvus_client, config)
    redis_client = providers.Singleton(get_redis_client, config)
    embedding_client = providers.Singleton(EmbeddingClient, config)
    reranker_client = providers.Singleton(RerankerClient, config)
    bm25_client = providers.Singleton(Bm25Client, redis_client=redis_client)
    # 워크스페이스 인제스트 — 텍스트 파서(config 토글)와 pgvector 엔진(외부타입 get_* 팩토리, fail-soft None)
    parser = providers.Singleton(get_parser, config)
    workspace_engine = providers.Singleton(get_workspace_engine, config)

    # Repository (벡터 store, 연결 주입) — Milvus(검색 전용) / pgvector(워크스페이스 문서)
    vector_search_milvus_repository = providers.Factory(VectorSearchMilvusRepository, milvus_client=milvus_client)
    workspace_chunk_repository = providers.Factory(
        WorkspaceChunkRepository,
        engine=workspace_engine,
        table=config.provided.WORKSPACE_TABLE,
        embedding_dim=config.provided.EMBEDDING_DIM,
    )

    # Service (repository + client 주입). use_real_api=false 면 MOCK 금융 문서로 폴백 (인프라 없이 단독 동작)
    # 토글 분리(#190): 큐레이션(Milvus) tool 은 USE_REAL_API, 워크스페이스(pgvector)는
    # WORKSPACE_REAL_API(미설정 시 USE_REAL_API 상속 — config 검증자가 bool 로 확정).
    vector_search_service = providers.Factory(
        VectorSearchService,
        vector_search_repository=vector_search_milvus_repository,
        embedding_client=embedding_client,
        reranker_client=reranker_client,
        bm25_client=bm25_client,
        use_real_api=config.provided.USE_REAL_API,
    )
    workspace_service = providers.Factory(
        WorkspaceService,
        workspace_repository=workspace_chunk_repository,
        embedding_client=embedding_client,
        parser=parser,
        use_real_api=config.provided.WORKSPACE_REAL_API,
    )

    router_modules = [
        "routers.vector_search.vector_search_router",
        "routers.workspace.workspace_router",
    ]
    wiring_config = containers.WiringConfiguration(modules=router_modules)
