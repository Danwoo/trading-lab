// app/api/common/system/author/[author_id]/menu/[menu_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isSysAdminAuthor } from "@/constants/protected";

/**
 * [DELETE] /api/system/author/[author_id]/menu/[menu_id]
 * 권한에서 메뉴 제거. 시스템관리자(001) 권한의 메뉴 매핑은 변경 불가.
 * 시스템관리자만 호출 가능 (글로벌 권한 메뉴 매핑은 워크스페이스 격리 영향이라 운영자 차단).
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { author_id, menu_id } = params;

  try {
    if (isSysAdminAuthor(author_id)) {
      return createErrorResponse({ message: "시스템관리자 권한의 메뉴 매핑은 변경할 수 없습니다." }, operation);
    }

    await prisma.authorMenu.delete({
      where: { author_id_menu_id: { author_id, menu_id } },
    });

    return createSuccessResponse({ message: "메뉴가 제거되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
