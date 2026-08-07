// app/api/common/system/workspace/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";

/**
 * [GET] /api/common/system/workspace
 * 워크스페이스 목록 조회
 */
const getHandler = async (req: NextRequest, _session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    const where = convertFilterToPrismaWhere(filter);
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ id: "asc" }];

    const [list, total_count] = await Promise.all([
      prisma.workspace.findMany({ where, orderBy, take, skip }),
      prisma.workspace.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      ...item,
      rn: (skip || 0) + index + 1,
    }));

    return createSuccessResponse({ items, total_count });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/common/system/workspace
 * 워크스페이스 생성
 */
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const data = await req.json();

    const workspace_code = String(data.workspace_code ?? "")
      .replace(/\s/g, "")
      .toLowerCase();

    const existing = await prisma.workspace.findUnique({ where: { workspace_code }, select: { id: true } });
    if (existing) {
      return createErrorResponse({ message: `이미 사용 중인 워크스페이스 코드입니다. (${workspace_code})` }, operation);
    }

    const workspace = await prisma.workspace.create({
      data: {
        workspace_code,
        workspace_nm: data.workspace_nm,
        use_at: data.use_at,
        reg_id: session.user.email,
        reg_dt: new Date(),
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "워크스페이스가 생성되었습니다.", data: workspace });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
