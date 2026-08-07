// app/api/common/system/code-group/[group_code]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [GET] /api/common/system/code-group/[group_code]
 * - group_code: 코드 그룹 식별자
 * - 특정 코드 그룹 정보 조회
 */
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const groupCode = await prisma.groupCode.findUnique({
      where: { group_code: params.group_code },
      include: {
        codes: {
          orderBy: { sort_ordr: "asc" },
        },
      },
    });

    if (!groupCode) {
      return createErrorResponse(
        {
          code: "P2025",
        },
        operation,
      );
    }

    return createSuccessResponse(groupCode, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

/**
 * [PUT] /api/common/system/code-group/[group_code]
 * - group_code: 코드 그룹 식별자
 * - 특정 코드 그룹 정보 수정
 * - 수정할 정보를 body로 전달
 */
const putHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "PUT";

  try {
    const body: { [key: string]: any } = await req.json();

    const allowedFields = ["group_code_nm", "group_code_dc", "use_at"];

    const updateData = Object.keys(body)
      .filter((key) => allowedFields.includes(key))
      .reduce((obj, key) => {
        obj[key] = body[key];
        return obj;
      }, {} as any);

    await prisma.groupCode.update({
      where: { group_code: params.group_code },
      data: {
        ...updateData,
        mod_dt: new Date(),
        mod_id: session.user.email,
      },
    });

    return createSuccessResponse({}, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

/**
 * [DELETE] /api/common/system/code-group/[group_code]
 * - group_code: 코드 그룹 식별자
 * - 특정 코드 그룹 삭제 (하위 코드들도 함께 삭제)
 */
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "DELETE";

  try {
    // 트랜잭션으로 하위 코드들과 그룹 코드 모두 삭제
    await prisma.$transaction(async (tx) => {
      // 1. 먼저 하위 코드들 삭제
      await tx.code.deleteMany({
        where: { group_code: params.group_code },
      });

      // 2. 그룹 코드 삭제
      await tx.groupCode.delete({
        where: { group_code: params.group_code },
      });
    });

    return createSuccessResponse({}, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const PUT = withAuth(putHandler, { requireSysAdmin: true });
export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
