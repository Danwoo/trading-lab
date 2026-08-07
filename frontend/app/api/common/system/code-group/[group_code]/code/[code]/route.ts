// app/api/common/system/code-group/[group_code]/code/[code]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [GET] /api/common/system/code-group/[group_code]/code/[code]
 * - group_code: 코드 그룹 식별자
 * - code: 코드 식별자
 * - 개별 코드 정보 조회
 * - 지정된 코드 그룹 내 특정 코드의 상세 정보 반환
 */
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const code = await prisma.code.findUnique({
      where: {
        group_code_code: {
          group_code: params.group_code,
          code: params.code,
        },
      },
      include: {
        group_code_ref: true,
      },
    });

    if (!code) {
      return createErrorResponse(
        {
          code: "P2025",
        },
        operation,
      );
    }

    return createSuccessResponse(code, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

/**
 * [PUT] /api/common/system/code-group/[group_code]/code/[code]
 * - group_code: 코드 그룹 식별자
 * - code: 코드 식별자
 * - 개별 코드 정보 수정
 * - 지정된 코드 그룹 내 특정 코드의 정보를 수정 (수정할 정보를 body로 전달)
 */
const putHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "PUT";

  try {
    const body: { [key: string]: any } = await req.json();

    const allowedFields = ["code_nm", "code_nm_eng", "code_dc", "sort_ordr", "use_at"];

    const updateData = Object.keys(body)
      .filter((key) => allowedFields.includes(key))
      .reduce((obj, key) => {
        obj[key] = body[key];
        return obj;
      }, {} as any);

    await prisma.code.update({
      where: {
        group_code_code: {
          group_code: params.group_code,
          code: params.code,
        },
      },
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
 * [DELETE] /api/common/system/code-group/[group_code]/code/[code]
 * - group_code: 코드 그룹 식별자
 * - code: 코드 식별자
 * - 개별 코드 삭제
 * - 지정된 코드 그룹 내 특정 코드 삭제
 */
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "DELETE";

  try {
    await prisma.code.delete({
      where: {
        group_code_code: {
          group_code: params.group_code,
          code: params.code,
        },
      },
    });

    return createSuccessResponse({}, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const PUT = withAuth(putHandler, { requireSysAdmin: true });
export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
