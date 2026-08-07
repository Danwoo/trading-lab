// proxy.ts
import { NextResponse, type NextRequest } from "next/server";
import { env } from "@/env";

type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

type PathRule = {
  path: string;
  methods?: readonly HttpMethod[];
  prefix?: boolean;
  exclude?: readonly string[];
};

const PUBLIC_RULES: readonly PathRule[] = [
  // 회원가입 플로우
  { path: "/api/common/email", methods: ["POST"] },
  { path: "/api/common/email/verify", methods: ["POST"] },
  { path: "/api/common/signup", methods: ["GET", "POST"] },

  // Better Auth 인증 플로우
  { path: "/api/auth/sign-in/", prefix: true },
  { path: "/api/auth/sign-up/", prefix: true },
  { path: "/api/auth/callback/", prefix: true },
  { path: "/api/auth/sign-out", methods: ["POST"] },
  { path: "/api/auth/get-session", methods: ["GET"] },
  { path: "/api/auth/token", methods: ["GET"] },
  { path: "/api/auth/verify-email", methods: ["GET"] },
  { path: "/api/auth/request-password-reset", methods: ["POST"] },
  { path: "/api/auth/reset-password", prefix: true },
  { path: "/api/auth/error", methods: ["GET"] },
  { path: "/api/auth/ok", methods: ["GET"] },
] as const;

function isPublicPath(pathname: string, method: HttpMethod): boolean {
  for (const rule of PUBLIC_RULES) {
    const pathMatch = rule.prefix ? pathname.startsWith(rule.path) : rule.path === pathname;
    if (pathMatch && (!rule.methods || rule.methods.includes(method))) {
      if (rule.exclude?.some((ex) => pathname.startsWith(ex))) continue;
      return true;
    }
  }
  return false;
}

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const method = (request.method ?? "GET") as HttpMethod;

  // 공개 경로는 통과
  if (isPublicPath(pathname, method)) {
    return NextResponse.next();
  }

  // Better Auth 세션 쿠키 확인 (optimistic check)
  const sessionCookie =
    request.cookies.get(`${env.APP_KEY}.session_token`) || request.cookies.get(`__Secure-${env.APP_KEY}.session_token`);

  if (!sessionCookie?.value) {
    // API 요청은 401 반환
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    }
    // 페이지 요청은 로그인으로 리다이렉트
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*", "/admin/:path*", "/user/:path*"],
};
