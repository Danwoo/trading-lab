// app/api/common/system/adminuser/[email]/author/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [GET] /api/system/adminuser/[email]/author
 * 사용자가 속한 권한 목록 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { email } = params;

  try {
    const members = await prisma.authorMember.findMany({
      where: { user_id: email },
      include: { author: true },
      orderBy: { author_id: "asc" },
    });

    const items = members.map((m) => ({
      author_id: m.author_id,
      author_nm: m.author?.author_nm ?? m.author_id,
    }));

    return createSuccessResponse({ items, total_count: items.length });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { scopeEmailParam: "email", requireOperatorOrAdmin: true });
