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
    BACKEND_SERVICE_URL: z.string(),
    DEV_ACTIVITY_SERVICE_URL: z.string().default(""),
    MULTI_AGENT_SERVICE_URL: z.string().default("http://localhost:8003"),
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

    // 공통 인프라
    NEXT_PUBLIC_FILE_SERVICE_URL: z.string(),
  },
  experimental__runtimeEnv: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_APP_EDITION: process.env.NEXT_PUBLIC_APP_EDITION,
    NEXT_PUBLIC_FILE_SERVICE_URL: process.env.NEXT_PUBLIC_FILE_SERVICE_URL,
  },
});
