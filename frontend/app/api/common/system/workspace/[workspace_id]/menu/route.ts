// app/api/common/system/workspace/[workspace_id]/menu/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu } from "@/constants/protected";

/**
 * [GET] /api/common/system/workspace/[workspace_id]/menu
 * 워크스페이스에 부여된 메뉴 목록 + 전체 메뉴 목록 (DualSelectGrid 용)
 * 시스템 메뉴(msys*)는 워크스페이스 매핑 대상이 아니므로 allMenus 에서 제외 (권한만으로 노출).
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const workspace_id = Number(params.workspace_id);

  try {
    const workspace = await prisma.workspace.findUnique({ where: { id: workspace_id } });
    if (!workspace) {
      return createErrorResponse({ message: "워크스페이스를 찾을 수 없습니다." }, operation);
    }

    const workspaceMenusRaw = await prisma.workspaceMenu.findMany({ where: { workspace_id } });

    const allMenusRaw = await prisma.menu.findMany({
      orderBy: [{ menu_level: "asc" }, { sort_ordr: "asc" }],
    });
    const allMenus = allMenusRaw
      .filter((m) => !isProtectedMenu(m.menu_id))
      .map((m) => ({ menu_id: m.menu_id, menu_nm: m.menu_nm, menu_level: m.menu_level ?? 1, use_at: m.use_at }));

    const menuMap = new Map(allMenusRaw.map((m) => [m.menu_id, m]));
    const workspaceMenus = workspaceMenusRaw.map((cm) => {
      const m = menuMap.get(cm.menu_id);
      return {
        menu_id: cm.menu_id,
        reg_dt: cm.reg_dt,
        menu: m ? { menu_nm: m.menu_nm, use_at: m.use_at } : undefined,
      };
    });

    return createSuccessResponse({ workspaceMenus, allMenus });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/common/system/workspace/[workspace_id]/menu
 * 워크스페이스에 메뉴 추가
 */
const postHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "POST";
  const workspace_id = Number(params.workspace_id);
  const data = await req.json();

  try {
    if (isProtectedMenu(data.menu_id)) {
      return createErrorResponse({ message: "시스템 메뉴는 워크스페이스에 부여할 수 없습니다." }, operation);
    }

    const existing = await prisma.workspaceMenu.findUnique({
      where: { workspace_id_menu_id: { workspace_id, menu_id: data.menu_id } },
    });

    if (existing) {
      return createErrorResponse({ message: "이미 등록된 메뉴입니다." }, operation);
    }

    const workspaceMenu = await prisma.workspaceMenu.create({
      data: {
        workspace_id,
        menu_id: data.menu_id,
        reg_id: session.user.email,
        reg_dt: new Date(),
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "메뉴가 추가되었습니다.", data: workspaceMenu });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
