// app/api/common/system/menu/[menu_id]/author/[author_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu } from "@/constants/protected";

/**
 * [DELETE] /api/common/system/menu/[menu_id]/author/[author_id]
 * 메뉴에서 권한 회수 (menu → author). 글로벌 매핑이라 시스템관리자만.
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { menu_id, author_id } = params;

  try {
    if (isProtectedMenu(menu_id)) {
      return createErrorResponse({ message: "시스템 메뉴는 권한별로 부여하지 않습니다." }, operation);
    }

    await prisma.authorMenu.delete({
      where: { author_id_menu_id: { author_id, menu_id } },
    });

    return createSuccessResponse({ message: "권한이 회수되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
