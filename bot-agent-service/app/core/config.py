"""설정 — 유일한 settings 경계. agent·service 는 config 주입으로 받는다.

**이 서비스만 `ANTHROPIC_API_KEY` 를 쓴다.** 다른 서비스의 LLM 경로(`LLM_BASE_URL`·`LLM_MODEL`,
OpenAI 호환)와 갈래가 다르므로 여기서 `LLM_*` 를 읽지 않는다 (결정 로그 2026-08-15).

이 키는 `build_options` 가 `env` 로 자식 프로세스에 **명시해서** 넘긴다. 다만 그것으로 다른
인증 경로가 닫히지는 않는다 — 기계에 Claude Code 로그인(`~/.claude/.credentials.json`)이 있으면
CLI 가 그것으로 인증할 수 있고, SDK 옵션으로는 그 파일을 가릴 수 없다(실측). 그래서 이 서비스를
**로컬 배포 모드 전용**으로 묶는 아래 결정이 그 잔여 위험의 실질적 경계다.

**로컬 배포 모드 전용이다.** 호스팅에서 셸 권한은 테넌트 격리를 무력화하므로(결정 2026-07-28)
이 서비스는 호스팅 모드에서 **띄우지 않는 것**으로 분리한다 — 라우트를 빼는 것보다 프로세스를
안 띄우는 편이 빠뜨릴 자리가 없다.
"""

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "production"
    SERVICE_NAME: str = "fullstack-bot-agent"
    VICTORIALOGS_URL: str = ""

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). SoT 는 process-compose.yaml 의 frontend PORT.
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # 인증 — frontend·backend 와 동일 JWT_SECRET (사용자 JWT 검증)
    JWT_SECRET: str = ""

    # ── Claude Agent SDK ───────────────────────────────────────────────────
    # 키는 **프로세스 환경변수**로만 온다. SDK 는 .env 를 자동으로 읽지 않으므로
    # pydantic-settings 가 읽어 두고, 에이전트를 띄울 때 프로세스 env 로 넘긴다.
    # 사용자의 claude.ai 로그인을 태우는 길은 약관이 막는다 (조사 결과 — 이슈 #150 코멘트).
    # 다만 **약관이 막는 것과 코드가 막는 것은 다르다** — 위 「인증」 문단이 그 차이를 적는다.
    ANTHROPIC_API_KEY: str = ""

    # 전략 파일 디렉터리 — 에이전트가 읽을 수 있는 유일한 자리 (규약 §1)
    STRATEGIES_DIR: str = ""

    # 대화 한 번이 돌 수 있는 최대 턴 수 — 폭주 시 비용 상한
    AGENT_MAX_TURNS: int = 12

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
        # AUTH_DEV_BYPASS 는 development 에서만 — 비-dev 기동 시 fail-fast
        if self.AUTH_DEV_BYPASS and self.APP_ENV != "development":
            raise ValueError("AUTH_DEV_BYPASS 는 development 환경에서만 허용됩니다.")
        return self


settings = Settings()
