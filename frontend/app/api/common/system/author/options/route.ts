// app/api/common/system/author/options/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

/**
 * [GET] /api/system/author/options
 * 전체 권한 목록 조회 (SelectBox 드롭다운용 - 페이지네이션 없음)
 * - 비시스템관리자는 시스템관리자 권한이 목록에서 숨겨짐
 */
const getHandler = async (_req: NextRequest, session: any) => {
  const operation = "GET";
  try {
    const where = session.user.isSysAdmin ? {} : { NOT: { author_id: SYS_ADMIN_AUTHOR_ID } };
    const items = await prisma.author.findMany({
      where,
      select: { author_id: true, author_nm: true },
      orderBy: { author_id: "asc" },
    });

    return createSuccessResponse({ items });
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
