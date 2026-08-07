// app/api/common/system/author/[author_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isSysAdminAuthor, isProtectedAuthor } from "@/constants/protected";

/**
 * [GET] /api/system/author/[author_id]
 * 권한 상세 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { author_id } = params;

  try {
    const author = await prisma.author.findUnique({
      where: { author_id },
    });

    if (!author) {
      return createErrorResponse({ message: "권한을 찾을 수 없습니다." }, operation);
    }

    return createSuccessResponse({
      ...author,
      is_sys_admin: isSysAdminAuthor(author_id),
      is_protected: isProtectedAuthor(author_id),
    });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [PUT] /api/system/author/[author_id]
 * 권한 수정
 */
const putHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "PUT";
  const { author_id } = params;
  const data = await req.json();

  try {
    const author = await prisma.author.update({
      where: { author_id },
      data: {
        author_nm: data.author_nm,
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "권한이 수정되었습니다.", data: author });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const PUT = withAuth(putHandler, { requireSysAdmin: true });

/**
 * [DELETE] /api/system/author/[author_id]
 * 권한 삭제 (시스템관리자 전용). 보호 권한(admin)은 삭제 불가. 사용자/메뉴 배정도 함께 정리.
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { author_id } = params;

  try {
    if (isProtectedAuthor(author_id)) {
      return createErrorResponse({ message: "시스템 권한은 삭제할 수 없습니다." }, operation);
    }

    await prisma.$transaction([
      prisma.authorMember.deleteMany({ where: { author_id } }),
      prisma.authorMenu.deleteMany({ where: { author_id } }),
      prisma.author.delete({ where: { author_id } }),
    ]);

    return createSuccessResponse({ message: "권한이 삭제되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
