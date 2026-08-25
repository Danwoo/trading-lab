// app/api/common/system/author/[author_id]/user/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { SYS_ADMIN_AUTHOR_ID, isSysAdminAuthor } from "@/constants/protected";
import { assertSameWorkspaceOrSysAdmin, invalidateUserSessions, normalizeEmail } from "@/lib/auth/authUtils";

/**
 * [GET] /api/system/author/[author_id]/user
 * 권한에 속한 사용자 목록 + 전체 사용자 목록 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { author_id } = params;

  try {
    const authorMembers = await prisma.authorMember.findMany({
      where: { author_id },
      include: {
        user: {
          select: {
            email: true,
            name: true,
            use_at: true,
            appr_at: true,
            workspace: { select: { workspace_nm: true } },
          },
        },
      },
    });

    const authorUsers = authorMembers.map((item) => ({
      author_id: item.author_id,
      user_id: item.user_id,
      user_nm: item.user?.name || "",
      use_at: item.user?.use_at ?? "Y",
      appr_at: item.user?.appr_at ?? "N",
      workspace_nm: item.user?.workspace?.workspace_nm ?? "",
    }));

    const allUsersRaw = await prisma.user.findMany({
      select: {
        email: true,
        name: true,
        use_at: true,
        appr_at: true,
        workspace: { select: { workspace_nm: true } },
      },
      orderBy: { email: "asc" },
    });

    const allUsers = allUsersRaw.map((item) => ({
      user_id: item.email,
      user_nm: item.name || "",
      use_at: item.use_at,
      appr_at: item.appr_at,
      workspace_nm: item.workspace?.workspace_nm ?? "",
    }));

    // 삭제 확인 창이 「이 권한만 가진 사용자」 영향을 말하려면(#356) 각 사용자의 **다른** 권한
    // 배정까지 세어야 한다 — 이 권한 하나만 있던 사용자는 삭제 순간 권한 0건으로 떨어진다.
    const userIds = authorMembers.map((m) => m.user_id);
    const soleAuthorUserCount = userIds.length
      ? (
          await prisma.authorMember.groupBy({
            by: ["user_id"],
            where: { user_id: { in: userIds } },
            _count: { author_id: true },
          })
        ).filter((row) => row._count.author_id === 1).length
      : 0;

    return createSuccessResponse({ authorUsers, allUsers, sole_author_user_count: soleAuthorUserCount });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/system/author/[author_id]/user
 * 권한에 사용자 추가
 */
const postHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "POST";
  const { author_id } = params;
  const data = await req.json();
  // `user_id` 는 이름과 달리 값이 이메일이다 — 경계에서 한 번 정규화한다. 이 라우트는
  // withAuth 의 `scopeEmailParam`(URL param 정규화) 경로를 안 타므로 여기서 직접 통과시킨다.
  // 안 하면 대문자로 온 주소가 `tn_user.email` 과 안 맞아, 조회는 "사용자를 찾을 수 없습니다"가
  // 되고 세션 무효화는 조용히 아무것도 안 한다 (#238 의 이메일 식별 축, #250·#221 과 같은 부류).
  const userEmail = normalizeEmail(typeof data.user_id === "string" ? data.user_id : "");

  try {
    if (isSysAdminAuthor(author_id)) {
      const isSysAdmin = await prisma.authorMember.count({
        where: { author_id: SYS_ADMIN_AUTHOR_ID, user_id: session.user.email },
      });
      if (!isSysAdmin) {
        return createErrorResponse(
          { message: "시스템관리자 권한의 사용자는 시스템관리자만 관리할 수 있습니다." },
          operation,
        );
      }
    }

    // 운영자: 자기 워크스페이스 사용자에게만 권한 부여 가능 (시스템관리자는 우회).
    // 소속 판정은 목록·단건 가드와 같은 술어(`workspaceScopedUserWhere`) 하나만 쓴다 — 여기만
    // 스칼라 `workspace_id` 단독으로 비교하면 멤버십으로만 소속된 사용자에게 권한을 못 준다 (#380).
    const scopeMsg = await assertSameWorkspaceOrSysAdmin(session, userEmail);
    if (scopeMsg) return createErrorResponse({ message: scopeMsg }, operation);

    const existing = await prisma.authorMember.findUnique({
      where: { author_id_user_id: { author_id, user_id: userEmail } },
    });

    if (existing) {
      return createErrorResponse({ message: "이미 부여된 권한입니다." }, operation);
    }

    const authorMember = await prisma.authorMember.create({
      data: {
        author_id,
        user_id: userEmail,
        reg_id: session.user.email,
        reg_dt: new Date(),
      },
    });

    // 권한 변경 시 BaSession 의 authorId denormalize 가 stale 해지므로 무효화
    await invalidateUserSessions(userEmail);

    return createSuccessResponse({ message: "사용자가 권한에 추가되었습니다.", data: authorMember });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireOperatorOrAdmin: true });
