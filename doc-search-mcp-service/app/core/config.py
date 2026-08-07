import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "doc-search-mcp-service"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend·devactivity 와 동일 JWT_SECRET (사용자/에이전트 JWT + 서비스 토큰 검증)
    JWT_SECRET: str = ""

    # false(기본): Milvus/Redis/임베딩/리랭커 없이 in-memory MOCK 금융 문서로 동작. true: 실 인프라 사용
    USE_REAL_API: bool = False

    # 워크스페이스(pgvector) 색인·검색 전용 실모드 토글 (#190). 미설정(None)이면 USE_REAL_API 를
    # 상속한다(기존 배포 무영향). 큐레이션(Milvus) 28 tool 은 USE_REAL_API 그대로 — 로컬처럼
    # Milvus 없이 임베딩·pg 만 있는 환경에서 워크스페이스만 실모드로 켤 때 이 값을 true 로 준다.
    # 주의: 빈 문자열(WORKSPACE_REAL_API=)은 bool 파싱 실패로 기동이 죽는다 — 미설정 또는 true/false 만.
    WORKSPACE_REAL_API: bool | None = None

    # Hybrid Topic Vector Search (USE_REAL_API=true 일 때만 사용)
    MILVUS_DB_HOST: str = ""
    MILVUS_DB_TOKEN: str = ""
    MILVUS_DB_NAME: str = "finance_doc_topic"
    REDIS_DB_HOST: str = ""
    # 포트 0·음수·65536 이상은 TCP 상 성립하지 않는 값 — 기동 시 거부해 연결 실패를 조기에 드러낸다 (#271 부류).
    REDIS_DB_PORT: int = Field(default=6379, gt=0, le=65535)
    REDIS_DB_PASSWORD: str = ""
    OPENAI_EMBEDDING_URL: str = ""
    OPENAI_EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    OPENAI_EMBEDDING_API_KEY: str = "EMPTY"
    OPENAI_RERANKER_URL: str = ""
    OPENAI_RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    OPENAI_API_KEY: str = ""

    # 사용자 워크스페이스 문서 인제스트 — pgvector 벡터 스토어 (WORKSPACE_REAL_API=true + host 설정 시 사용).
    # host 가 비어 있으면 pg 없이 MOCK 경로로 동작 (Milvus/Redis 와 동일한 fail-soft 정책).
    DOC_VECTOR_DB_HOST: str = ""
    DOC_VECTOR_DB_PORT: int = Field(default=5432, gt=0, le=65535)
    DOC_VECTOR_DB_NAME: str = ""
    DOC_VECTOR_DB_USER: str = ""
    DOC_VECTOR_DB_PASSWORD: str = ""
    WORKSPACE_TABLE: str = "workspace_doc_chunk"
    EMBEDDING_DIM: int = 1024

    # 텍스트 추출 파서 선택 — "opensource"(pypdf, 기본) / "upstage"(후속 슬라이스, 미구현)
    DOC_PARSER: str = "opensource"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'production')}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _inherit_workspace_real_api(self) -> "Settings":
        # 미설정이면 USE_REAL_API 상속 — 이 검증자 이후 WORKSPACE_REAL_API 는 항상 bool 이다.
        # (토글을 하나만 쓰던 기존 배포는 값을 안 주므로 동작이 그대로다 — #190)
        if self.WORKSPACE_REAL_API is None:
            self.WORKSPACE_REAL_API = self.USE_REAL_API
        return self

    @model_validator(mode="after")
    def _require_jwt_secret_outside_dev(self) -> "Settings":
        # 비-dev 에서 빈 JWT_SECRET 으로 기동 금지 (추측 가능한 비밀로 인증이 서는 것 방지 — fail-fast)
        if self.APP_ENV != "development" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET 이 비어 있습니다 (frontend·backend 와 동일값 필요).")
        return self

    @model_validator(mode="after")
    def _forbid_dev_bypass_outside_dev(self) -> "Settings":
        # AUTH_DEV_BYPASS 는 development 에서만 — 비-dev 기동 시 fail-fast (인증 우회가 프로덕션에 서는 것 방지)
        if self.AUTH_DEV_BYPASS and self.APP_ENV != "development":
            raise ValueError("AUTH_DEV_BYPASS 는 development 환경에서만 허용됩니다.")
        return self


settings = Settings()
