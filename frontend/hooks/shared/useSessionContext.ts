import { useSession } from "@/lib/auth/auth-client";
import { SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

/**
 * 현재 로그인 사용자의 권한/워크스페이스 컨텍스트 즉시 노출.
 * - BaSession 의 denormalize 된 authorId/workspaceId 를 그대로 사용 (API 호출 없음)
 * - isSysAdmin: 시스템관리자 여부 (워크스페이스 격리 우회용)
 */
export function useSessionContext() {
  const { data: session } = useSession();
  const authorId = (session as any)?.session?.authorId ?? null;
  const workspaceId = (session as any)?.session?.workspaceId ?? null;
  return {
    authorId,
    workspaceId,
    isSysAdmin: authorId === SYS_ADMIN_AUTHOR_ID,
    isLoaded: !!session,
  };
}
