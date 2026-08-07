// app/api/common/system/workspace/[workspace_id]/menu/[menu_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [DELETE] /api/common/system/workspace/[workspace_id]/menu/[menu_id]
 * 워크스페이스에서 메뉴 제거
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const workspace_id = Number(params.workspace_id);
  const { menu_id } = params;

  try {
    await prisma.workspaceMenu.delete({
      where: { workspace_id_menu_id: { workspace_id, menu_id } },
    });

    return createSuccessResponse({ message: "메뉴가 제거되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
