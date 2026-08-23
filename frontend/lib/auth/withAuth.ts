// lib/auth/withAuth.ts
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth/auth";
import { headers } from "next/headers";
import { createErrorResponse } from "@/utils/common/api/responses";
import { SYS_ADMIN_AUTHOR_ID, GENERAL_ADMIN_AUTHOR_ID } from "@/constants/protected";
import { assertSameWorkspaceOrSysAdmin, assertTargetNotSysAdmin, normalizeEmail } from "@/lib/auth/authUtils";
import { findUnsafePathSegment } from "@/lib/auth/safePathSegment";
import { resolveAccountContext } from "@/lib/auth/accountContext";
import { env } from "@/env";

// 일반 API 핸들러 (JSON 응답)
type JsonHandler = (request: NextRequest, session: any, params?: any) => Promise<NextResponse> | NextResponse;

// 파일 스트림 핸들러 (바이너리 응답)
type StreamHandler = (request: NextRequest, session: any, params?: any) => Promise<Response> | Response;

// 통합 핸들러 타입
type AuthenticatedHandler = JsonHandler | StreamHandler;

interface WithAuthOptions {
  /** true 면 시스템관리자만 핸들러 진입 허용. URL 직접 호출 우회 차단용. */
  requireSysAdmin?: boolean;
  /** true 면 시스템관리자 또는 운영자(일반관리자)만 진입 허용. 일반 user 직접 API 호출 차단용. */
  requireOperatorOrAdmin?: boolean;
  /**
   * 지정 시 해당 URL param 의 사용자가 요청자와 같은 워크스페이스인지 검증 (시스템관리자는 우회).
   * 워크스페이스 격리가 필요한 단건 라우트(adminuser/[email]/*)의 정책을 핸들러 밖 한 곳에 선언.
   */
  scopeEmailParam?: string;
  /**
   * scopeEmailParam 과 함께 사용. 대상이 시스템관리자 계정이면 비-시스템관리자 요청자를 차단.
   * 워크스페이스 격리만으론 같은 워크스페이스 시스템관리자를 못 막으므로 write(PUT/DELETE)에서 추가 방어.
   */
  protectSysAdminTarget?: boolean;
}

/**
 * 인증 실패 응답(401) — 쿠키 캐시를 **함께 버린다.**
 *
 * 인가 게이트는 캐시를 우회하므로 API 는 곧바로 401 이 되지만, 화면의 `useSession()` 은
 * Better Auth 의 `/api/auth/get-session` 을 보고 그건 캐시를 읽는다. 지우지 않으면 최대
 * 5분간 "로그인된 것처럼 보이는데 모든 요청이 401" 인 상태가 남는다. 청크 쿠키까지 지우려고
 * 접미사 몇 개를 함께 만료시킨다 (없는 쿠키를 만료시키는 것은 무해하다).
 */
function unauthenticated(operation: string) {
  const response = createErrorResponse({ code: "AUTH", message: "Authentication required" }, operation);
  const base = `${env.APP_KEY}.session_data`;
  for (const name of [base, ...Array.from({ length: 5 }, (_, i) => `${base}.${i}`)]) {
    response.cookies.set(name, "", { path: "/", maxAge: 0 });
  }
  return response;
}

export function withAuth(handler: AuthenticatedHandler, opts: WithAuthOptions = {}) {
  return async (request: NextRequest, props: any) => {
    const operation = "AUTH";

    const sessionResponse = await auth.api.getSession({
      headers: await headers(),
      returnHeaders: true,
      // 쿠키 캐시(JWE)는 **최적화지 인가의 정본이 아니다.** 이 한 줄이 빠지면 Better Auth 는
      // 서명된 쿠키만 읽고 끝내서, 세션 행을 지우는 무효화(권한 회수·계정 비활성·관리자
      // 강제 종료·비밀번호 재설정)가 캐시 수명만큼 통째로 무시된다 — 실측 최대 5분 (#354).
      // 캐시 자체는 켜 둔 채다: 화면의 `useSession()`·`/api/auth/get-session` 같은 비인가
      // 조회는 계속 쿠키로 답한다. 뚫는 자리는 인가 게이트인 여기 하나뿐이다.
      query: { disableCookieCache: true },
    });

    const session = sessionResponse?.response;

    if (!session || !session.user) {
      return unauthenticated(operation);
    }

    // 권한·계정 상태의 정본은 **지금의 DB** 다. 세션 행이 담은 authorId/workspaceId 는 로그인
    // 시점의 스냅샷이라, 무효화를 부르지 않는 변경 경로가 하나라도 있으면 그 사용자는 옛 권한을
    // 무기한 유지한다 (`DELETE /api/common/system/author/[author_id]` 가 실제로 그랬다 — #354).
    const account = await resolveAccountContext((session.user as any).id);
    if (account.block) {
      return unauthenticated(operation);
    }

    const authorId = account.authorId;
    const workspaceId = account.workspaceId;

    // 스냅샷과 어긋나면 끊는다. 살아 있는 값으로 계속 진행하지 않는 이유는 백엔드로 나가는
    // JWT 때문이다 — `set-auth-jwt` 는 Better Auth 가 **세션 행**으로 서명하므로, 여기서만
    // 값을 갈아끼우면 프론트는 새 권한으로 판정하고 백엔드는 옛 workspace_id 로 격리한다.
    // 재로그인시키는 편이 두 축을 다시 맞추는 유일하게 안전한 길이다.
    if (
      authorId !== ((session.session as any)?.authorId ?? null) ||
      workspaceId !== ((session.session as any)?.workspaceId ?? null)
    ) {
      return unauthenticated(operation);
    }

    const accessToken = sessionResponse?.headers?.get("set-auth-jwt") ?? undefined;

    // 기존 session 인터페이스 호환을 위해 accessToken 포함
    const sessionWithToken = {
      ...session,
      user: {
        ...session.user,
        authorId,
        workspaceId,
        isSysAdmin: authorId === SYS_ADMIN_AUTHOR_ID,
      },
      accessToken,
    };

    if (opts.requireSysAdmin && !sessionWithToken.user.isSysAdmin) {
      return createErrorResponse({ code: "FORBIDDEN", message: "권한이 없습니다." }, operation);
    }

    if (
      opts.requireOperatorOrAdmin &&
      !sessionWithToken.user.isSysAdmin &&
      sessionWithToken.user.authorId !== GENERAL_ADMIN_AUTHOR_ID
    ) {
      return createErrorResponse({ code: "FORBIDDEN", message: "권한이 없습니다." }, operation);
    }

    let unwrappedParams: any = {};
    if (props && props.params) {
      unwrappedParams = props.params instanceof Promise ? await props.params : props.params;
    }

    const unsafeKey = findUnsafePathSegment(unwrappedParams);
    if (unsafeKey) {
      return createErrorResponse({ message: `${unsafeKey} 값이 올바르지 않습니다.` }, operation);
    }

    // 워크스페이스 격리 — 지정 param 의 사용자가 요청자 워크스페이스 소속인지 (시스템관리자 우회)
    if (opts.scopeEmailParam) {
      // URL param 을 여기서 한 번 정규화해 이 옵션을 쓰는 모든 라우트(adminuser/[email]/*)가
      // 같은 규칙으로 조회한다 — 라우트마다 따로 정규화하면 그중 하나가 빠질 수 있다 (#250 의 교훈).
      const email = normalizeEmail(unwrappedParams[opts.scopeEmailParam] ?? "");
      unwrappedParams[opts.scopeEmailParam] = email;
      const scopeMsg = await assertSameWorkspaceOrSysAdmin(sessionWithToken, email);
      if (scopeMsg) return createErrorResponse({ message: scopeMsg }, operation);

      // 대상이 시스템관리자 계정이면 비-시스템관리자 요청자 차단
      if (opts.protectSysAdminTarget && !sessionWithToken.user.isSysAdmin) {
        const protectMsg = await assertTargetNotSysAdmin(email);
        if (protectMsg) return createErrorResponse({ message: protectMsg }, operation);
      }
    }

    return await handler(request, sessionWithToken, unwrappedParams);
  };
}
