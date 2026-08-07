# ── [가이드 2/8] core/config.py — 설정 (유일한 settings 경계). client/service 는 config 주입으로 받음 ──
# 복사 후: SERVICE_NAME 을 새 도메인으로. 외부 API/DB 가 필요하면 *_BASE_URL·*_API_KEY 필드를 추가
#   (+ .env.{development,staging,production} 3종에 동일 키). echo 템플릿은 외부 의존 0 이라 추가 필드 없음.
# 함정: JWT_SECRET 은 frontend·backend·소비자와 byte-identical(불일치=401) · _require_jwt_secret_outside_dev
#   fail-fast 삭제 금지(빈 비밀로 인증 서는 사고 차단) · 시크릿 평문 기본값 금지(.env 에만). 상세: CLAUDE.md "환경".

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "fullstack-template-mcp"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend·소비자(에이전트)와 동일 JWT_SECRET (사용자/에이전트 JWT + 서비스 토큰 검증)
    JWT_SECRET: str = ""

    # (외부 API/DB 가 필요하면 여기에 *_BASE_URL·*_API_KEY 필드를 추가하고 .env 3종에 동일 키를 둔다)

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


settings = Settings()
