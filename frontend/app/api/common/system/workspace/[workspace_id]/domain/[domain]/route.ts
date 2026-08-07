// app/api/common/system/workspace/[workspace_id]/domain/[domain]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// 도메인은 등록(POST) / 삭제(DELETE) 만 가능. 수정(PUT) 제거 — use_at 토글 컬럼 없앰.

/**
 * [DELETE] /api/common/system/workspace/[workspace_id]/domain/[domain]
 * 도메인 삭제
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";

  try {
    const target = decodeURIComponent(params.domain);
    await prisma.workspaceDomain.delete({ where: { domain: target } });
    return createSuccessResponse({ message: "도메인이 삭제되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
