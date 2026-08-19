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
    SERVICE_NAME: str = "backend-service"

    # 로컬 개발 전용 JWT 우회 (default false, development 밖에서는 기동 거부)
    AUTH_DEV_BYPASS: bool = False

    # CORS 허용 origin (와일드카드 금지 — 명시 목록). 기본값 포트는 로컬 프론트 포트와 lockstep 이고
    # SoT 는 process-compose.yaml 의 frontend PORT 다 (scripts/verify_dev_port_hygiene.py 가 대조).
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3010"]

    # SQL 서버 설정
    BACKEND_SQL_DB_DRIVER: str
    # ODBC 드라이버명은 pyodbc(MSSQL) 경로에서만 쓰인다 — PostgreSQL(psycopg) 에서는 불필요 (#166)
    BACKEND_SQL_DB_ODBC_DRIVER: str = ""
    BACKEND_SQL_DB_HOST: str
    # 포트 0·음수·65536 이상은 TCP 상 성립하지 않는 값 — 기동 시 거부해 연결 실패를 조기에 드러낸다 (#271 부류).
    BACKEND_SQL_DB_PORT: int = Field(gt=0, le=65535)
    BACKEND_SQL_DB_NAME: str
    BACKEND_SQL_DB_USER: str
    BACKEND_SQL_DB_PASSWORD: str

    # file 모듈 — SFTP 서버 설정
    SFTP_HOST: str
    SFTP_PORT: int = Field(gt=0, le=65535)
    SFTP_USERNAME: str
    SFTP_PASSWORD: str
    # 업로드 허용 루트. 클라이언트가 준 base_path 는 이 아래로 강제된다 (resolve_upload_base).
    SFTP_BASE_PATH: str = "/upload"

    # 업로드 파일당 최대 크기 (MB) — 초과 시 413. 정본 판정은 파싱 후 실측 검사(FileService.upload_files).
    # 0 이하는 모든 업로드를 무조건 거절하는 무의미한 값이라 기동 시 거부한다 (#271).
    MAX_UPLOAD_SIZE_MB: int = Field(default=20, gt=0)

    # 요청 바디(멀티파트 전체) 남용 차단선 (MB). 파일당 한도가 아니라 "이 이상은 정상 사용이 아니다"의 상한이다.
    # 20MB 파일 25개(=최대 배치의 5배)까지 통과하므로 정상 다중파일 배치는 막지 않고, 리버스 프록시가 허용하는
    # 2g 급 요청만 파싱 전에 잘라 대역폭·temp 디스크 소모를 막는다 (#109).
    # 0 이하는 파일당 한도(MAX_UPLOAD_SIZE_MB>0)보다 항상 작아 아래 _forbid_body_cap_below_file_limit 에서도
    # 걸리지만, 그 검증 없이도 그 자체로 무의미한 값이라 독립적으로 거부한다 (#271).
    MAX_REQUEST_BODY_SIZE_MB: int = Field(default=512, gt=0)

    # 한 요청에 올릴 수 있는 파일 개수 남용 차단선. 파일당 크기 한도(MAX_UPLOAD_SIZE_MB)와 독립적으로,
    # 작은 파일 수천 개가 바디 상한(MAX_REQUEST_BODY_SIZE_MB) 아래로 통과해 파싱·SFTP 비용을 개수만큼
    # 무는 것을 막는다 (#144). 프론트 UI 배치 상한(maxFileCount 5·3)의 20배로 잡아 정상 다중파일 배치는
    # 절대 막지 않고 수천 개 남용만 차단한다 — 바디 크기 검사와 상호보완(큰 파일은 바디 상한, 작은 파일은 개수 상한).
    MAX_UPLOAD_FILES: int = 100

    # 시세 소스에 우리를 밝히는 연락처 문자열 — **비밀값이 아니다.** SEC 는 API 키 대신
    # "연락처가 담긴 User-Agent"를 요구하고(전자공시 접근 정책), 이메일이 없는 UA 는 403 으로
    # 거절한다(실측). 예: "trading-lab/1.0 (contact: you@example.com)". 비면 SEC
    # 어댑터가 capability 에 "연락처 미설정" 사유를 실어 스스로 막는다.
    MARKET_DATA_CONTACT: str = ""

    # 데이터 소스 API 키 — 전역 `.env` 설정이 정본이다 (2026-08-07 리드 결정). 이 제품은 로컬
    # 배포판 우선이라 「각자 자기 컴퓨터에서 자기 키로」 굴린다. 비워 두면 그 소스가 기동을 막지
    # 않고 `capabilities()` 가 "키 없음" + 발급 경로를 사유로 낸다(FR-013·FR-021).
    # **읽는 곳은 `services/data_key/` 하나다** — 어댑터는 `settings.` 를 읽지 않고 키를 생성자로
    # 주입받는다(MD-AD-20 의 유효한 절반). 이 설정 이름이 그 밖에 나오면
    # `scripts/verify_data_key_env_boundary.py` 가 잡는다.
    MARKET_DATA_GOKR_SERVICE_KEY: str = ""
    MARKET_DATA_ALPACA_KEY: str = ""
    # 없어도 동작한다 — 있으면 OpenFIGI 배치 한도만 올라간다.
    MARKET_DATA_OPENFIGI_KEY: str = ""
    # 토스증권 Open API — OAuth2 Client Credentials 쌍 (data_key_service 가 합성 주입)
    TOSS_CLIENT_ID: str = ""
    TOSS_CLIENT_SECRET: str = ""
    # 주문 계열 호출 개폐 — 가드(providers/toss/live_guard.py)는 이 값을 **환경변수로 직접** 읽는다
    # (설정 배관과 독립인 마지막 방어층). 기본 닫힘이며 기본값 변경은 리드 승인 사항이다.
    TRADING_LIVE_ENABLED: bool = False

    # doc-search-mcp-service (리서치 문서 인제스트·청크 회수 — 내부 서비스 토큰 호출)
    DOC_SEARCH_SERVICE_URL: str = "http://localhost:8008"

    # chat·report 모듈 — MCP 서버 (비면 portfolio-mcp-service 등록 안됨)
    MCP_SERVERS: list[McpServer] = []

    # LLM (OpenAI 호환 /chat/completions)
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = "EMPTY"

    # SMTP (frontend 와 동일 SMTP)
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = Field(default=465, gt=0, le=65535)
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: str = ""

    JWT_SECRET: str

    VICTORIALOGS_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'production')}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def max_upload_bytes(self) -> int:
        """업로드 파일당 최대 크기(바이트). MAX_UPLOAD_SIZE_MB 를 단일 소스로 파생 — MB→bytes 변환을 한 곳에만 둔다."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def max_request_body_bytes(self) -> int:
        """요청 바디 남용 차단선(바이트). 정밀 한도가 아니다 — 파일당 판정은 max_upload_bytes 실측 검사가 한다."""
        return self.MAX_REQUEST_BODY_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _forbid_body_cap_below_file_limit(self) -> "Settings":
        # 바디 차단선이 파일당 한도보다 낮으면 정상 단일 파일도 조기 거절된다 — 설정 실수를 기동 시 잡는다.
        if self.MAX_REQUEST_BODY_SIZE_MB < self.MAX_UPLOAD_SIZE_MB:
            raise ValueError(
                f"MAX_REQUEST_BODY_SIZE_MB({self.MAX_REQUEST_BODY_SIZE_MB})는 "
                f"MAX_UPLOAD_SIZE_MB({self.MAX_UPLOAD_SIZE_MB}) 이상이어야 합니다."
            )
        return self

    @model_validator(mode="after")
    def _forbid_nonpositive_file_count(self) -> "Settings":
        # 개수 상한이 1 미만이면 정상 업로드까지 전부 거절된다 — 설정 실수를 기동 시 잡는다.
        if self.MAX_UPLOAD_FILES < 1:
            raise ValueError(f"MAX_UPLOAD_FILES({self.MAX_UPLOAD_FILES})는 1 이상이어야 합니다.")
        return self

    @model_validator(mode="after")
    def _forbid_dev_bypass_outside_dev(self) -> "Settings":
        # AUTH_DEV_BYPASS 는 development 에서만 — 비-dev 기동 시 fail-fast (인증 우회가 프로덕션에 서는 것 방지)
        if self.AUTH_DEV_BYPASS and self.APP_ENV != "development":
            raise ValueError("AUTH_DEV_BYPASS 는 development 환경에서만 허용됩니다.")
        return self


settings = Settings()
