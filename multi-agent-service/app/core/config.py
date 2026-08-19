import os

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServer(BaseModel):
    """MCP 서버 연결정보."""

    name: str
    url: str
    path: str = "/mcp"
    enabled: bool = True


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "multi-agent-service"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend·MCP 서버들과 동일 JWT_SECRET (사용자 JWT 검증 + 서비스 토큰 발급)
    JWT_SECRET: str = ""

    # 공통 DB `fintech` — frontend Prisma 소유인 `frontend.ai_chat_history` 를 멀티턴 히스토리로
    # read-only 조회한다. 남의 스키마라 쿼리에서 스키마를 수식한다(커넥션 search_path 는 기본값, #166).
    MULTI_AGENT_SQL_DB_DRIVER: str = "postgresql+psycopg"
    # ODBC 드라이버명은 pyodbc(MSSQL) 경로에서만 쓰인다 — PostgreSQL(psycopg) 에서는 불필요 (#166)
    MULTI_AGENT_SQL_DB_ODBC_DRIVER: str = ""
    MULTI_AGENT_SQL_DB_HOST: str = ""
    # 포트 0·음수·65536 이상은 TCP 상 성립하지 않는 값 — 기동 시 거부해 연결 실패를 조기에 드러낸다 (#271 부류).
    MULTI_AGENT_SQL_DB_PORT: int = Field(default=5432, gt=0, le=65535)
    MULTI_AGENT_SQL_DB_NAME: str = ""
    MULTI_AGENT_SQL_DB_USER: str = ""
    MULTI_AGENT_SQL_DB_PASSWORD: str = ""

    # MCP 서버 (비면 도구 0개로 기동 — sub-agent 는 LLM 지식 전용)
    MCP_SERVERS: list[McpServer] = []

    # LLM 제공자 — 받는 사람마다 가진 키가 다르다 (#226). 표는 `clients/llm/providers.py`.
    # 비우면 `custom` 이라 종전대로 BASE_URL 을 직접 읽는다 (뒤로 호환).
    ROUTER_LLM_PROVIDER: str = ""
    GENERATOR_LLM_PROVIDER: str = ""
    # 주 제공자가 죽었을 때 넘어갈 자리. `<provider>|<model>|<key>` 형식을 쉼표로 잇는다
    # (예: `groq|llama-3.3-70b-versatile|gsk_…`). 비우면 폴백 없음 — 실패가 그대로 드러난다.
    LLM_FALLBACKS: str = ""

    # LLM — Router(소형: ReAct/plan/가드레일) / Generator(대형: 답변 생성·평가) 2계층
    ROUTER_LLM_BASE_URL: str = ""
    ROUTER_LLM_API_KEY: str = "EMPTY"
    ROUTER_LLM_MODEL: str = ""
    # Router/Planner 의 vLLM 전용 extra_body(chat_template_kwargs.enable_thinking=false) 전송 토글.
    # 자가 서빙 vLLM(Qwen reasoning 억제)은 true 필수, Groq 등 상용 OpenAI 호환 API 는 400 거부라 false (#188 Phase C).
    ROUTER_LLM_VLLM_COMPAT: bool = True
    GENERATOR_LLM_BASE_URL: str = ""
    GENERATOR_LLM_API_KEY: str = "EMPTY"
    GENERATOR_LLM_MODEL: str = ""

    # 도메인 토글 — instrument/financials/risk/market 중 활성화할 목록
    MULTI_AGENT_DOMAINS: list[str] = ["instrument", "financials", "risk", "market"]

    # 멀티턴 히스토리 상한 — 무제한 로드로 인한 토큰·지연·메모리 폭주 방지.
    # (question,answer) 쌍 최대 개수. SQL LIMIT 캡으로 대화 길이와 무관하게 최근 N턴만 적재.
    MA_HISTORY_MAX_TURNS: int = 10
    # 노드당 히스토리 프롬프트 주입 총량 상한(문자) — 메시지당 2000자 캡과 이중 상한.
    # 미캡 시 k=20 × 2000자 = 노드당 최대 4만 자가 clarify·plan·answer 에 중복 주입된다 (#207).
    MA_HISTORY_MAX_CHARS: int = 8000

    # 실행 파라미터 (타임아웃·재시도·루프 상한)
    MA_GUARDRAIL_TIMEOUT_S: float = 15.0
    MA_CLARIFY_TIMEOUT_S: float = 15.0
    MA_AGENT_TIMEOUT_S: float = 120.0
    MA_AGENT_MAX_RETRIES: int = 1
    MA_SUB_AGENT_TIMEOUT_S: float = 60.0
    MA_PLAN_TIMEOUT_S: float = 60.0
    MA_ANSWER_TIMEOUT_S: float = 60.0
    MA_DELEGATE_MAX_CALLS: int = 2
    MA_REACT_RECURSION_LIMIT: int = 8
    # 재계획 — 순차 의존 질문에서 직전 결과를 보고 후속 stage 를 동적 추가하는 횟수 상한 (0=비활성)
    MA_MAX_REPLAN: int = 2

    # Hierarchical Map-Reduce — 활성 도메인 수가 임계 이상이면 도메인별 sub-answer 후 통합
    MA_MAP_REDUCE_DOMAIN_THRESHOLD: int = 3
    MA_MAP_CONCURRENCY: int = 3
    MA_MAP_TIMEOUT_S: float = 50.0
    MA_REDUCE_MODE: str = "full"  # "full" | "disabled"(sub-answer concat, 긴급 회피)

    # 가드레일 / 레이트리밋
    MA_GUARDRAIL_ENABLED: bool = True
    MA_RATE_LIMIT_PER_MINUTE: int = 30
    MA_MAX_CONCURRENT_STREAMS: int = 10

    # 응답 캐시 — 비결정적·시점 의존 응답이라 프로덕션은 false 권장 (개발·데모용)
    MA_RESPONSE_CACHE_ENABLED: bool = False
    MA_RESPONSE_CACHE_TTL_S: float = 300.0
    MA_RESPONSE_CACHE_MAX_ENTRIES: int = 128

    # trace 이벤트 metadata (sub_agent_calls·domain_hits·composite_score) 생성 토글
    MA_TRACE_TOKEN_USAGE: bool = True

    # langfuse 관측 — 세 키가 모두 있으면 graph 실행을 langfuse 로 trace (서버 OTEL 지원 필요)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = ""

    # LangSmith 관측 — API_KEY 있으면 main 이 os.environ 주입 → langchain 자동 trace
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "multi-agent"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'production')}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    @model_validator(mode="after")
    def _require_positive_guardrail_timeout(self) -> "Settings":
        # 가드레일이 fail-closed(#338)로 바뀌어 0·음수는 asyncio.wait_for(timeout<=0)가 매 요청을
        # 즉시 타임아웃시켜 전체 채팅이 상시 차단된다 — 오설정을 기동 시점에 fail-fast 로 잡는다.
        if self.MA_GUARDRAIL_TIMEOUT_S <= 0:
            raise ValueError(
                "MA_GUARDRAIL_TIMEOUT_S 는 0보다 커야 합니다 (fail-closed 전환 후 0 이하는 전체 요청 상시 차단)."
            )
        return self


settings = Settings()
