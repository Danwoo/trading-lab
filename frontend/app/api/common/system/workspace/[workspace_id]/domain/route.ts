// app/api/common/system/workspace/[workspace_id]/domain/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { isPublicEmailDomain } from "@/constants/protected";

/**
 * [GET] /api/common/system/workspace/[workspace_id]/domain
 * 워크스페이스 도메인 목록 조회
 */
const getHandler = async (req: NextRequest, _session: any, params: any) => {
  const operation = "GET";

  try {
    const id = Number(params.workspace_id);
    const workspace = await prisma.workspace.findUnique({ where: { id } });
    if (!workspace) {
      return createErrorResponse({ code: "P2025" }, operation);
    }

    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    // 사용자 필터를 AND 로 묶는다 — 얕은 스프레드로 합치면 같은 키(`workspace_id`)를 담은
    // 클라 filter 가 URL 경로가 정한 스코프를 통째로 덮어써, 1번 워크스페이스를 가리키는 URL 이
    // 99번을 조회한다 (adminuser/route.ts · workspace/[workspace_id]/user/route.ts 와 같은 규약, #399).
    const baseWhere = { workspace_id: id };
    const userFilter = convertFilterToPrismaWhere(filter);
    const where = Object.keys(userFilter).length > 0 ? { AND: [baseWhere, userFilter] } : baseWhere;
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ domain: "asc" }];

    const [list, total_count] = await Promise.all([
      prisma.workspaceDomain.findMany({ where, orderBy, take, skip }),
      prisma.workspaceDomain.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      ...item,
      rn: (skip || 0) + index + 1,
    }));

    return createSuccessResponse({ items, total_count, workspace_id: id, workspace_nm: workspace.workspace_nm });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/common/system/workspace/[workspace_id]/domain
 * 워크스페이스 도메인 생성
 */
const postHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "POST";

  try {
    const body = await req.json();
    const domain = String(body.domain ?? "")
      .toLowerCase()
      .trim();

    // 형식 검증 (DB-only 우회 시도 시 마지막 방어선)
    if (!/^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$/.test(domain)) {
      return createErrorResponse({ message: "올바른 도메인 형식이 아닙니다 (예: example.com)." }, operation);
    }

    // 공용/개인 이메일 도메인은 워크스페이스 도메인으로 등록 불가
    if (isPublicEmailDomain(domain)) {
      return createErrorResponse(
        { message: "공용 이메일 도메인은 워크스페이스 도메인으로 등록할 수 없습니다." },
        operation,
      );
    }

    const id = Number(params.workspace_id);

    // 다른 워크스페이스가 이미 사용 중인지 명시적 안내
    const existingDomain = await prisma.workspaceDomain.findUnique({
      where: { domain },
      select: { workspace_id: true },
    });
    if (existingDomain) {
      const msg =
        existingDomain.workspace_id === id
          ? "이미 등록된 도메인입니다."
          : "다른 워크스페이스가 사용 중인 도메인입니다.";
      return createErrorResponse({ message: msg }, operation);
    }

    const result = await prisma.workspaceDomain.create({
      data: {
        domain,
        workspace_id: id,
        reg_id: session.user.email,
        reg_dt: new Date(),
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "도메인이 등록되었습니다.", data: result });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
