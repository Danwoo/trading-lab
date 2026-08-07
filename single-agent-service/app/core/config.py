# ── [가이드 1/9] core/config.py — 설정 (유일한 settings 경계). client/agent 는 config 주입으로 받음 ──
# 무엇: env 파일을 읽어 Settings 한 곳에 모은다. 그 아래 client/service 는 settings 를 직접 import 하지
#   않고 container 가 주입한다.
# 복사 후: SERVICE_NAME, MCP_SERVERS 기본값, ROUTER_LLM_* 를 새 도메인 값으로. (+ .env 3종 동일 키)
# 함정: JWT_SECRET 은 frontend·backend·MCP 서버와 byte-identical — 불일치 시 MCP 서버가 401 로 막는다 ·
#   비-dev 빈 JWT_SECRET fail-fast 삭제 금지 · MCP_SERVERS 가 비면 tool 0개(fail-soft, LLM 지식만으로 답).

import os

from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServer(BaseModel):
    """MCP 서버 연결정보. path 기본 /mcp, enabled=false 면 연결 제외."""

    name: str
    url: str
    path: str = "/mcp"
    enabled: bool = True


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "fullstack-single-agent"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend·MCP 서버와 동일 JWT_SECRET (사용자 JWT 검증 + 서비스 토큰 발급)
    JWT_SECRET: str = ""

    # MCP 서버 (비면 tool 0개 — fail-soft). 기본값은 web-mcp-service(Tavily 웹검색)
    MCP_SERVERS: list[McpServer] = [McpServer(name="web", url="http://localhost:8007")]

    # LLM — 단일 에이전트라 하나만 (OpenAI 호환 /chat/completions, vLLM/litellm)
    ROUTER_LLM_BASE_URL: str = ""
    ROUTER_LLM_MODEL: str = ""
    ROUTER_LLM_API_KEY: str = "EMPTY"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'production')}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _require_jwt_secret_outside_dev(self) -> "Settings":
        # 비-dev 에서 빈 JWT_SECRET 으로 기동 금지 (추측 가능한 비밀로 인증이 서는 것 방지 — fail-fast)
        if self.APP_ENV != "development" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET 이 비어 있습니다 (frontend·backend·MCP 서버와 동일값 필요).")
        return self

    @model_validator(mode="after")
    def _forbid_dev_bypass_outside_dev(self) -> "Settings":
        # AUTH_DEV_BYPASS 는 development 에서만 — 비-dev 기동 시 fail-fast (인증 우회가 프로덕션에 서는 것 방지)
        if self.AUTH_DEV_BYPASS and self.APP_ENV != "development":
            raise ValueError("AUTH_DEV_BYPASS 는 development 환경에서만 허용됩니다.")
        return self


settings = Settings()
