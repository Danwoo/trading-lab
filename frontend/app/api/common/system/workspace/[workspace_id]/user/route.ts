// app/api/common/system/workspace/[workspace_id]/user/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { workspaceScopedUserWhere } from "@/lib/auth/authUtils";

/**
 * [GET] /api/common/system/workspace/[workspace_id]/user
 * 워크스페이스 소속 사용자 목록 (read-only, 시스템관리자가 워크스페이스 상세에서 멤버 조회 용)
 *
 * 소속 판정은 `workspaceScopedUserWhere` 하나만 쓴다 — 스칼라 `workspace_id` 단독으로 비교하면
 * 멤버십으로만 소속된 사용자가 이 목록에서 빠져, 같은 사람이 관리 목록에는 보이는데 여기선
 * 안 보이는 상태가 된다 (#380).
 */
const getHandler = async (req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const workspace_id = Number(params.workspace_id);

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    // 사용자 필터를 AND 로 묶는다 — 얕은 스프레드로 합치면 클라가 보낸 filter 의 `OR` 키가
    // 스코프 술어의 `OR` 를 통째로 덮어써 워크스페이스 경계가 사라진다 (adminuser/route.ts 와 같은 규약).
    const scopeWhere = workspaceScopedUserWhere(workspace_id);
    const userFilter = convertFilterToPrismaWhere(filter);
    const where = Object.keys(userFilter).length > 0 ? { AND: [scopeWhere, userFilter] } : scopeWhere;
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ reg_dt: "desc" }];

    const [list, total_count] = await Promise.all([
      prisma.user.findMany({
        where,
        orderBy,
        take,
        skip,
        select: {
          email: true,
          name: true,
          dept: true,
          use_at: true,
          appr_at: true,
          reg_dt: true,
          author_members: { select: { author: { select: { author_nm: true } } } },
        },
      }),
      prisma.user.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      email: item.email,
      name: item.name,
      dept: item.dept,
      use_at: item.use_at,
      appr_at: item.appr_at,
      reg_dt: item.reg_dt,
      author_nm: item.author_members.map((m) => m.author.author_nm).join(", "),
      rn: (skip || 0) + index + 1,
    }));

    return createSuccessResponse({ items, total_count });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });
