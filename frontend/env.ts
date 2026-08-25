import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

/**
 * 환경변수 + 서비스별 기본값 (백엔드 core/config.py 의 pydantic-settings 와 동등한 역할)
 * - 환경변수 누락 시 default 값 사용 (default 없으면 빌드 시 에러)
 * - 빌드/런타임 시 타입 검증
 * - 클라이언트 노출은 NEXT_PUBLIC_* 만 허용
 */
export const env = createEnv({
  server: {
    // 인프라
    NODE_ENV: z.enum(["development", "production"]).default("development"),
    NEXT_RUNTIME: z.string().default(""),
    APP_KEY: z.string().default("fstpl"),
    SERVICE_NAME: z.string().default("fullstack-web"),
    VICTORIALOGS_URL: z.string().default(""),
    BETTER_AUTH_TRUSTED_ORIGINS: z.string().default(""),

    // 공통 인프라
    EMAIL_HOST: z.string(),
    EMAIL_PORT: z.string(),
    EMAIL_USER: z.string(),
    EMAIL_PASSWORD: z.string(),
    EMAIL_SECRET: z.string(),
    BETTER_AUTH_URL: z.string(),
    BETTER_AUTH_SECRET: z.string(),
    JWT_SECRET: z.string(),
    DATABASE_URL: z.string(),

    // 프로젝트 특화
    /**
     * 통합 앱(`backend-service`)의 **서버→서버** 주소. `app/api/external/backend/**` 프록시가
     * 이 하나만 쓴다 — 예전엔 흡수된 서비스 이름(`DEV_ACTIVITY_SERVICE_URL`)이 같은 앱을
     * 따로 가리켜, 한쪽만 옮기면 관리자 화면 두 개가 「총 0건」으로 조용히 죽었다 (#361).
     *
     * 브라우저에서 그 앱을 부르는 자리는 이 값을 쓸 수 없다 — 서버 전용이라 번들에 안 실리고,
     * 배포에서는 컨테이너 이름(`http://fullstack-backend:8000`)이라 브라우저가 못 푼다.
     * 그쪽은 `NEXT_PUBLIC_FILE_SERVICE_URL` 이 따로 진다(아래 `client` 블록).
     */
    BACKEND_SERVICE_URL: z.string(),
    MULTI_AGENT_SERVICE_URL: z.string().default("http://localhost:8003"),
    // 봇 만들기 대화 — 로컬 배포 모드 전용이라 없을 수도 있다(그때 화면이 이유를 보여준다).
    BOT_AGENT_SERVICE_URL: z.string().default("http://localhost:8011"),
    PORTFOLIO_MCP_SERVICE_URL: z.string().default("http://localhost:8002"),
    MARKET_DATA_MCP_SERVICE_URL: z.string().default("http://localhost:8004"),
    DISCLOSURE_MCP_SERVICE_URL: z.string().default("http://localhost:8005"),
    NEWS_MCP_SERVICE_URL: z.string().default("http://localhost:8006"),
    WEB_MCP_SERVICE_URL: z.string().default("http://localhost:8007"),
    DOC_SEARCH_MCP_SERVICE_URL: z.string().default("http://localhost:8008"),
  },
  client: {
    // 인프라
    NEXT_PUBLIC_APP_NAME: z.string().default("Fintech AI Platform"),
    // 제품 에디션: SAAS(멀티테넌트·셀프가입) / OEM(단일워크스페이스·승인제). 미지정 시 OEM.
    NEXT_PUBLIC_APP_EDITION: z.enum(["SAAS", "OEM"]).default("OEM"),

    /**
     * 통합 앱의 **브라우저→서버** 주소. `BACKEND_SERVICE_URL` 과 같은 앱을 가리키지만 **다른
     * 축**이라 합치지 않는다 — 이 값은 번들에 실려 사용자의 브라우저가 직접 부르고, 비워 두면
     * 같은 출처의 `/file-service` 로 떨어져 nginx 가 통합 앱으로 넘긴다.
     */
    NEXT_PUBLIC_FILE_SERVICE_URL: z.string(),
  },
  experimental__runtimeEnv: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_APP_EDITION: process.env.NEXT_PUBLIC_APP_EDITION,
    NEXT_PUBLIC_FILE_SERVICE_URL: process.env.NEXT_PUBLIC_FILE_SERVICE_URL,
  },
});
