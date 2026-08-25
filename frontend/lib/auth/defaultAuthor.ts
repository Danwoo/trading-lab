import type { Prisma } from "@/prisma/generated/client";
import { GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID } from "@/constants/protected";

/**
 * 계정이 서는 자리 — 기본 권한은 이 둘로만 정해진다.
 *
 * - `workspace`: 그 계정의 기본 워크스페이스가 **자기 개인 것**인가(`personal`), 남이 운영하는
 *   **공용** 것인가(`shared`), 아직 없는가(`none`).
 * - `approved`: `tn_user.appr_at === "Y"`. 승인 전 계정은 로그인 자체가 막혀 있어(`resolveAccountContext`)
 *   권한을 미리 줄 이유가 없고, 승인하는 순간 붙는다.
 */
export type WorkspaceKind = "personal" | "shared" | "none";
export type AccountPlacement = { workspace: WorkspaceKind; approved: boolean };

/**
 * **계정을 만들거나 승인할 때 자동으로 붙는 권한 — 규칙은 여기 하나다.**
 *
 * 리드 결정 2026-08-23(#341)과 보완 2026-08-24 를 그대로 옮긴 것이다:
 * - 자기 개인 워크스페이스의 주인 → `SIGNUP_AUTHOR_ID`(운영자). 게스트를 주면 실험대·시세·
 *   관심종목의 저장·실행이 전부 403 이라 「봇 하나를 만들어 저장」이 닫힌다.
 * - 남의 공용 워크스페이스에 들어간 계정 → `GUEST_AUTHOR_ID`(읽기전용 게스트). 운영자를 주면
 *   초대 없이 그 워크스페이스의 쓰기와 사용자관리(같은 워크스페이스 계정의 수정·삭제)가 열린다.
 *   쓰기를 열지는 그 워크스페이스 운영자가 권한관리에서 판단한다.
 * - 워크스페이스가 없는 계정도 게스트다 — 주인이 아닌 것은 같고, 워크스페이스를 받기 전에는
 *   어차피 제품 API 가 막혀 있어(JWT 가 `workspace_id` 를 요구) 더 열 것이 없다.
 * - 승인 전 → `null`(아직 주지 않는다). OEM 가입·관리자가 「대기」로 만든 계정이 여기다.
 *
 * 계정을 만드는 경로가 셋(가입·관리자 생성·관리자 수정의 승인/배정)인데 예전엔 각자 다른 규칙을
 * 들고 있었다 — 가입은 운영자, 수정은 게스트, 생성은 **아무것도 안 줘서** 로그인은 되는데 제품
 * 화면이 통째로 닫혔다(#355). 세 경로가 전부 `grantDefaultAuthor` 를 부르고, 역할 상수를 라우트가
 * 직접 고르지 않는 것은 `tests/regressions/355-default-author-paths.test.ts` 가 소스를 훑어 잠근다.
 *
 * 관리자가 권한관리·소속 권한 탭에서 **골라서** 주는 것(`author/[author_id]/user`)은 기본값이
 * 아니라 명시적 부여라 이 규칙 밖이다.
 */
export function defaultAuthorIdFor(placement: AccountPlacement): string | null {
  if (!placement.approved) return null;
  return placement.workspace === "personal" ? SIGNUP_AUTHOR_ID : GUEST_AUTHOR_ID;
}

/**
 * 워크스페이스 id 가 어느 자리인지 읽는다. `is_personal` 이 판정 술어다 — 개인 워크스페이스는
 * 사용자 1명이 소유하고(`ensurePersonalWorkspace`), 관리자 배정은 개인 워크스페이스를 받지
 * 않으므로(`assertAssignableWorkspace`) 「이 계정의 기본 워크스페이스가 개인 것」이면 그 주인이다.
 * 없는 id(지워진 워크스페이스)는 `none` 으로 본다.
 */
export async function resolveWorkspaceKind(
  db: Prisma.TransactionClient,
  workspaceId: number | null | undefined,
): Promise<WorkspaceKind> {
  if (workspaceId == null) return "none";
  const workspace = await db.workspace.findUnique({ where: { id: workspaceId }, select: { is_personal: true } });
  if (!workspace) return "none";
  return workspace.is_personal ? "personal" : "shared";
}

/**
 * 규칙이 고른 기본 권한을 **없으면** 붙인다. 이미 그 권한이 있으면 그대로 두고, 규칙이 `null`
 * 이면 아무것도 하지 않는다. 돌려주는 값은 규칙이 고른 권한 id 다(붙였든 이미 있었든) —
 * 부르는 쪽이 「무엇이 붙어야 했나」를 알 수 있게.
 *
 * `db` 는 트랜잭션 클라이언트를 받는다 — 가입·생성처럼 계정 만들기가 한 트랜잭션일 때 그 안에서
 * 돌아야 앞 조각(사용자 행)만 남고 권한만 빠지는 반쪽이 생기지 않는다.
 */
export async function grantDefaultAuthor(
  db: Prisma.TransactionClient,
  args: { email: string; placement: AccountPlacement; actorEmail: string },
): Promise<string | null> {
  const authorId = defaultAuthorIdFor(args.placement);
  if (authorId === null) return null;

  const already = await db.authorMember.count({ where: { user_id: args.email, author_id: authorId } });
  if (already > 0) return authorId;

  const now = new Date();
  await db.authorMember.create({
    data: {
      author_id: authorId,
      user_id: args.email,
      reg_id: args.actorEmail,
      reg_dt: now,
      mod_id: args.actorEmail,
      mod_dt: now,
    },
  });
  return authorId;
}
