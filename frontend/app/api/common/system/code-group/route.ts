// app/api/common/system/code-group/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";

/**
 * [GET] /api/common/system/code-group
 * - 코드 그룹 목록 조회 (페이징, 필터링 지원)
 */
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    const where = convertFilterToPrismaWhere(filter);
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ group_code: "asc" }];

    const groupCodes = await prisma.groupCode.findMany({
      take,
      skip,
      where,
      orderBy,
      include: {
        codes: {
          orderBy: { sort_ordr: "asc" },
        },
      },
    });

    const items = groupCodes.map((data, index) => ({
      ...data,
      rn: (skip || 0) + index + 1,
    }));

    const total_count = take ? await prisma.groupCode.count({ where }) : items.length;

    const result = {
      items: items,
      total_count: total_count,
    };

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

/**
 * [POST] /api/common/system/code-group
 * - 코드 그룹 생성
 */
const postHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "POST";

  try {
    const body: { [key: string]: any } = await req.json();

    const allowedFields = ["group_code", "group_code_nm", "group_code_dc", "use_at"];

    const createData = Object.keys(body)
      .filter((key) => allowedFields.includes(key))
      .reduce((obj, key) => {
        obj[key] = body[key];
        return obj;
      }, {} as any);

    createData.group_code = String(createData.group_code ?? "")
      .replace(/\s/g, "")
      .toLowerCase();

    const existing = await prisma.groupCode.findUnique({
      where: { group_code: createData.group_code },
      select: { group_code: true },
    });
    if (existing) {
      return createErrorResponse({ message: `이미 사용 중인 그룹코드입니다. (${createData.group_code})` }, operation);
    }

    const result = await prisma.groupCode.create({
      data: {
        ...createData,
        reg_dt: new Date(),
        mod_dt: new Date(),
        reg_id: session.user.email,
        mod_id: session.user.email,
      },
    });

    return createSuccessResponse(
      {
        data: result,
      },
      operation,
    );
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const POST = withAuth(postHandler, { requireSysAdmin: true });
