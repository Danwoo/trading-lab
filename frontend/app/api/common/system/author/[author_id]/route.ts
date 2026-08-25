// app/api/common/system/author/[author_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isSysAdminAuthor, isProtectedAuthor } from "@/constants/protected";
import { invalidateSessionsForUsers } from "@/lib/auth/authUtils";

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

    // 이 권한을 달고 있던 사람들 — 트랜잭션이 지우기 전에 집어 둔다.
    const members = await prisma.authorMember.findMany({ where: { author_id }, select: { user_id: true } });

    await prisma.$transaction([
      prisma.authorMember.deleteMany({ where: { author_id } }),
      prisma.authorMenu.deleteMany({ where: { author_id } }),
      prisma.author.delete({ where: { author_id } }),
    ]);

    // 권한을 통째로 지우는 것은 그 권한을 가진 **모든 사용자에게서 회수**하는 것과 같다.
    // 사용자 단위 회수 경로(`author/[author_id]/user/[user_id]`)는 세션을 무효화하는데 여기만
    // 안 했다 — 같은 클래스의 마지막 구멍이었다 (#354).
    await invalidateSessionsForUsers(members.map((m) => m.user_id));

    return createSuccessResponse({ message: "권한이 삭제되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
