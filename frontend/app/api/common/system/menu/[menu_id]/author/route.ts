// app/api/common/system/menu/[menu_id]/author/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu, isSysAdminAuthor } from "@/constants/protected";

/**
 * [GET] /api/common/system/menu/[menu_id]/author
 * 메뉴에 설정된 권한 목록 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { menu_id } = params;

  try {
    const authorMenus = await prisma.authorMenu.findMany({
      where: { menu_id },
      include: { author: true },
      orderBy: { author_id: "asc" },
    });

    const items = authorMenus.map((m) => ({
      author_id: m.author_id,
      author_nm: m.author?.author_nm ?? m.author_id,
    }));

    return createSuccessResponse({ items, total_count: items.length });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/common/system/menu/[menu_id]/author
 * 메뉴에 권한 부여 (menu → author). 글로벌 매핑이라 시스템관리자만.
 * - 시스템 메뉴(msys*)는 권한별 부여 안 함 (AUTO_SYSTEM_MENUS 로 자동)
 * - 시스템관리자(admin) 권한은 모든 메뉴 접근하므로 별도 부여 안 함
 */
const postHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "POST";
  const { menu_id } = params;
  const data = await req.json();

  try {
    if (isProtectedMenu(menu_id)) {
      return createErrorResponse(
        { message: "시스템 메뉴는 권한별로 부여하지 않습니다 (코드 매핑으로 자동 접근)." },
        operation,
      );
    }
    if (isSysAdminAuthor(data.author_id)) {
      return createErrorResponse(
        { message: "시스템관리자 권한은 모든 메뉴에 접근하므로 별도 부여하지 않습니다." },
        operation,
      );
    }

    const existing = await prisma.authorMenu.findUnique({
      where: { author_id_menu_id: { author_id: data.author_id, menu_id } },
    });
    if (existing) {
      return createErrorResponse({ message: "이미 부여된 권한입니다." }, operation);
    }

    const authorMenu = await prisma.authorMenu.create({
      data: { author_id: data.author_id, menu_id, reg_id: session.user.email, reg_dt: new Date() },
    });

    return createSuccessResponse({ message: "권한이 부여되었습니다.", data: authorMenu });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
