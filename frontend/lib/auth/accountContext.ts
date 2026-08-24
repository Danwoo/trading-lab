// lib/auth/accountContext.ts
import { prisma } from "@/lib/prisma/client";
import { AUTHOR_PRIORITY, SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

/**
 * 접근을 막는 계정 상태. 로그인 훅이 던지는 `APIError` 메시지와 문자열을 맞춘다 —
 * 로그인 거절 사유와 세션 중단 사유가 같은 어휘를 쓰게 해서 로그를 대조할 수 있다.
 */
export type AccountBlock = "RejectedUser" | "PendingApproval" | "InactiveUser" | "InactiveWorkspace";

export type AccountContext =
  | { block: AccountBlock; authorId: null; workspaceId: null }
  | { block: null; authorId: string | null; workspaceId: number | null };

/**
 * 「지금 이 사용자는 무엇을 할 수 있는가」의 **단일 술어** — DB 를 읽어 대표 권한·선택
 * 워크스페이스·차단 사유를 낸다.
 *
 * 로그인 훅(`auth.ts` 의 `session.create.before`)과 인가 게이트(`withAuth`)가 **같은 함수**를
 * 부른다. 두 곳에 같은 규칙을 두 벌로 두면 한쪽만 고쳐져 갈린다 — 실제로 갈려 있었다:
 * 로그인은 `use_at`·`appr_at`·워크스페이스 활성을 봤는데 그 뒤 요청은 아무것도 안 봐서,
 * 권한 회수·계정 비활성이 **로그인 시점의 스냅샷**에 밀려 소급되지 않았다 (#354).
 */
export async function resolveAccountContext(userId: string): Promise<AccountContext> {
  const blocked = (block: AccountBlock): AccountContext => ({ block, authorId: null, workspaceId: null });

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      use_at: true,
      appr_at: true,
      email: true,
      workspace_id: true,
      workspace: { select: { use_at: true } },
      // 기본 멤버십은 사용자당 1행이어야 하지만 DB 가 강제하지 못한다 (Prisma 스키마로
      // partial unique index 를 표현할 수 없어 `prisma db push` 경로에 심을 자리가 없다 — #253).
      // 그래서 정렬을 못 박는다: 불변식이 깨져도 요청마다 테넌트가 바뀌지는 않게 한다.
      workspace_members: {
        where: { is_default: true },
        select: { workspace_id: true, workspace: { select: { use_at: true } } },
        orderBy: { workspace_id: "asc" },
        take: 1,
      },
    },
  });

  // 사용자 행이 없으면 승인 대기와 같이 취급한다 — 로그인 화면이 문구를 갖고 있는 값은
  // 이 넷뿐이라(`Login.tsx`), 여기서만 나오는 다섯 번째 값을 만들면 그 화면에 날 것의
  // 에러가 뜬다 (#224). 인가 게이트는 사유와 무관하게 401 이므로 판정에는 영향이 없다.
  if (!user) return blocked("PendingApproval");
  if (user.appr_at === "R") return blocked("RejectedUser");
  if (user.appr_at !== "Y") return blocked("PendingApproval");
  if (user.use_at === "N") return blocked("InactiveUser");

  const memberships = await prisma.authorMember.findMany({
    where: { user_id: user.email },
    select: { author_id: true },
  });
  const authorIds = memberships.map((m) => m.author_id);

  // 대표 권한: 행동 권한 우선순위로 먼저 집고 없으면 자유 권한 fallback (숫자 정렬 비의존)
  const authorId = AUTHOR_PRIORITY.find((a) => authorIds.includes(a)) ?? authorIds[0] ?? null;

  // 세션이 담는 것은 "소속"이 아니라 "지금 선택된 워크스페이스" — 기본 멤버십이 결정하고,
  // 아직 멤버십이 없는 계정은 사용자 행의 워크스페이스로 떨어진다.
  const defaultMembership = user.workspace_members[0];
  const selectedWorkspace = defaultMembership
    ? { id: defaultMembership.workspace_id, use_at: defaultMembership.workspace.use_at }
    : user.workspace
      ? { id: user.workspace_id, use_at: user.workspace.use_at }
      : null;

  // 워크스페이스 비활성 시 사용자도 접근 불가 — 단 시스템관리자(admin)는 무관하게 통과
  if (authorId !== SYS_ADMIN_AUTHOR_ID && selectedWorkspace && selectedWorkspace.use_at !== "Y") {
    return blocked("InactiveWorkspace");
  }

  return { block: null, authorId, workspaceId: selectedWorkspace?.id ?? null };
}
