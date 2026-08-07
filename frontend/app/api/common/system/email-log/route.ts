import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { workspaceScopedEmailWhere } from "@/lib/auth/authUtils";

/**
 * [GET] /api/common/system/email-log
 * 시스템관리자: 전체 / 운영자: 자기 워크스페이스 사용자에게 발송된 로그만
 */
const getHandler = async (req: NextRequest, session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    // 운영자: 자기 워크스페이스 등록 사용자 이메일 + 워크스페이스 등록 도메인 OR 매칭 —
    // 조립은 공유 헬퍼(workspaceScopedEmailWhere) 하나로 모은다. 라우트가 직접 조립하면
    // 대소문자 비교 규칙이 갈릴 수 있다(#221).
    const tenantWhere = session.user.isSysAdmin ? {} : await workspaceScopedEmailWhere(session.user.workspaceId ?? -1);

    // 사용자 필터를 AND 로 묶는다 — filter 의 OR 키가 tenantWhere OR 를 덮어써 전 워크스페이스 로그가 노출되는 우회 차단.
    const userFilter = convertFilterToPrismaWhere(filter);
    const where = Object.keys(userFilter).length > 0 ? { AND: [tenantWhere, userFilter] } : tenantWhere;
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ reg_dt: "desc" }];

    const [list, total_count] = await Promise.all([
      prisma.emailLog.findMany({ take, skip, where, orderBy }),
      prisma.emailLog.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      ...item,
      rn: (skip || 0) + index + 1,
    }));

    return createSuccessResponse({ items, total_count });
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
