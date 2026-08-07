// app/api/common/system/author/[author_id]/user/[user_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { SYS_ADMIN_AUTHOR_ID, isSysAdminAuthor } from "@/constants/protected";
import {
  assertSameWorkspaceOrSysAdmin,
  checkLastActiveSysAdmin,
  invalidateUserSessions,
  normalizeEmail,
} from "@/lib/auth/authUtils";

/**
 * [DELETE] /api/system/author/[author_id]/user/[user_id]
 * 권한에서 사용자 제거
 */
const deleteHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "DELETE";
  const { author_id } = params;
  // `user_id` 는 이름과 달리 값이 이메일이다 — POST 짝(../route.ts)과 같은 자리에서 정규화한다.
  // 이 라우트는 withAuth 의 `scopeEmailParam` 을 안 쓰므로(제거 대상이 URL 3번째 세그먼트) 여기서 통과시킨다.
  const user_id = normalizeEmail(typeof params.user_id === "string" ? params.user_id : "");

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

    // 운영자: 자기 워크스페이스 사용자의 권한만 제거 가능 (시스템관리자는 우회).
    // 소속 판정은 목록·단건 가드와 같은 술어(`workspaceScopedUserWhere`) 하나만 쓴다 — 여기만
    // 스칼라 `workspace_id` 단독으로 비교하면 멤버십으로만 소속된 사용자의 권한을 못 거둔다 (#380).
    const scopeMsg = await assertSameWorkspaceOrSysAdmin(session, user_id);
    if (scopeMsg) return createErrorResponse({ message: scopeMsg }, operation);

    if (isSysAdminAuthor(author_id)) {
      const guardMsg = await checkLastActiveSysAdmin(user_id);
      if (guardMsg) return createErrorResponse({ message: guardMsg }, operation);
    }

    await prisma.authorMember.delete({
      where: { author_id_user_id: { author_id, user_id } },
    });

    // 권한 변경 시 BaSession 의 authorId denormalize 가 stale 해지므로 무효화
    await invalidateUserSessions(user_id);

    return createSuccessResponse({ message: "사용자가 권한에서 제거되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

// user_id 는 이름과 달리 실제 값이 이메일이다(위 핸들러가 email 컬럼으로 조회). 경로 세그먼트
// 가드(#298)가 3차부터 값 형태를 보지 않으므로(탈출 값 두 개만 차단) 별도 선언은 불필요하다.
export const DELETE = withAuth(deleteHandler, { requireOperatorOrAdmin: true });
