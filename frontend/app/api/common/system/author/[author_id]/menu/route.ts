// app/api/common/system/author/[author_id]/menu/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu, isSysAdminAuthor } from "@/constants/protected";

/**
 * [GET] /api/system/author/[author_id]/menu
 * 권한에 연결된 메뉴 목록 + 전체 메뉴 목록 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { author_id } = params;

  try {
    const author = await prisma.author.findUnique({ where: { author_id } });
    if (!author) {
      return createErrorResponse({ message: "권한을 찾을 수 없습니다." }, operation);
    }

    const authorMenus = await prisma.authorMenu.findMany({
      where: { author_id },
      include: { menu: true },
    });

    const allMenus = await prisma.menu.findMany({
      orderBy: [{ menu_level: "asc" }, { sort_ordr: "asc" }],
    });

    return createSuccessResponse({ authorMenus, allMenus });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/system/author/[author_id]/menu
 * 권한에 메뉴 추가
 */
const postHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "POST";
  const { author_id } = params;
  const data = await req.json();

  try {
    if (isSysAdminAuthor(author_id)) {
      return createErrorResponse({ message: "시스템관리자 권한의 메뉴 매핑은 변경할 수 없습니다." }, operation);
    }
    if (isProtectedMenu(data.menu_id)) {
      return createErrorResponse(
        { message: "시스템 메뉴는 권한별로 부여하지 않습니다 (코드 매핑으로 자동 접근)." },
        operation,
      );
    }

    const existing = await prisma.authorMenu.findUnique({
      where: { author_id_menu_id: { author_id, menu_id: data.menu_id } },
    });

    if (existing) {
      return createErrorResponse({ message: "이미 등록된 메뉴입니다." }, operation);
    }

    const authorMenu = await prisma.authorMenu.create({
      data: {
        author_id,
        menu_id: data.menu_id,
        reg_id: session.user.email,
        reg_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "메뉴가 추가되었습니다.", data: authorMenu });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
