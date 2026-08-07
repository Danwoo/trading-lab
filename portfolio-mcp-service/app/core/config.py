import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "fullstack-portfolio-mcp"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend·multi-agent 와 동일 JWT_SECRET (사용자/에이전트 JWT + 서비스 토큰 검증)
    JWT_SECRET: str = ""

    # 브로커리지/포트폴리오 데이터 소스 — 기본은 in-memory MOCK (API 키 없이 동작).
    # USE_REAL_API=true 일 때만 외부 브로커리지 REST API 를 호출한다.
    USE_REAL_API: bool = False
    BROKERAGE_API_BASE_URL: str = ""  # 예: https://api.broker.example.com/v1
    BROKERAGE_API_TOKEN: str = ""  # 브로커리지 read 토큰 (Bearer)

    # 환율(FX) 소스 — market-data-mcp 의 /market/fx REST. 기준통화 환산 시에만 호출(실패는 fail-soft → unconverted).
    # 빈 값이면 FX 조회 비활성(교차통화는 전부 unconverted). market-data-mcp 는 기본 MOCK 환율 반환.
    MARKET_DATA_MCP_URL: str = "http://localhost:8004"

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
    def _require_brokerage_api_when_real(self) -> "Settings":
        # USE_REAL_API=true 면 외부 브로커리지 연결정보가 있어야 한다 (없으면 MOCK 로 두라는 의미 — fail-fast)
        if self.USE_REAL_API and not (self.BROKERAGE_API_BASE_URL and self.BROKERAGE_API_TOKEN):
            raise ValueError("USE_REAL_API=true 이면 BROKERAGE_API_BASE_URL·BROKERAGE_API_TOKEN 이 필요합니다.")
        return self


settings = Settings()
