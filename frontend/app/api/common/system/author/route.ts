// app/api/common/system/author/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { isSysAdminAuthor, isProtectedAuthor } from "@/constants/protected";

/**
 * [GET] /api/system/author
 * 권한 목록 조회 (서버사이드 페이징 지원). 권한관리는 시스템관리자 전용 메뉴.
 */
const getHandler = async (req: NextRequest, _session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    // 합칠 스코프 술어가 없는 전역 목록이라 필터를 그대로 쓴다 (code-group·workspace·menu 와 같은
    // 형태). 스프레드로 감싸지 않는다 — 이 파일에 base 술어가 생기는 날 `{ ...base, ...filter }`
    // 로 한 글자 늘리는 것이 #399 의 결함이므로, 그 형태를 아예 남겨두지 않는다.
    const where = convertFilterToPrismaWhere(filter);
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ author_id: "asc" }];

    const [list, total_count] = await Promise.all([
      prisma.author.findMany({ where, orderBy, take, skip }),
      prisma.author.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      ...item,
      rn: (skip || 0) + index + 1,
      is_sys_admin: isSysAdminAuthor(item.author_id),
      is_protected: isProtectedAuthor(item.author_id),
    }));

    return createSuccessResponse({ items, total_count });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/system/author
 * 권한 생성 (시스템관리자 전용). author_id 는 전역 PK — 워크스페이스 무관.
 */
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const data = await req.json();

    const existing = await prisma.author.findUnique({
      where: { author_id: data.author_id },
      select: { author_id: true },
    });
    if (existing) {
      return createErrorResponse({ message: `이미 사용 중인 권한 ID입니다. (${data.author_id})` }, operation);
    }

    const author = await prisma.author.create({
      data: {
        author_id: data.author_id,
        author_nm: data.author_nm,
        reg_id: session.user.email,
        reg_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "권한이 생성되었습니다.", data: author });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
