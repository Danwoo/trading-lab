// app/api/common/system/menu/navigation/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu, AUTO_SYSTEM_MENUS_BY_AUTHOR } from "@/constants/protected";

interface NavItem {
  id: string;
  text: string;
  icon?: string;
  path?: string;
  items?: NavItem[];
}

/**
 * [GET] /api/system/menu/navigation
 * 로그인한 사용자의 권한에 따라 접근 가능한 메뉴를 NavItem[] 형태로 반환
 * menu_level 1 → 폴더(대분류), 2 → 프로그램(leaf)
 */
const getHandler = async (_req: NextRequest, session: any) => {
  const operation = "GET";
  try {
    const userEmail = session.user.email;
    const isSysAdmin = session.user.isSysAdmin;

    let userMenuIds: Set<string> = new Set();
    if (!isSysAdmin) {
      const authorMembers = await prisma.authorMember.findMany({
        where: { user_id: userEmail },
        select: { author_id: true },
      });
      if (authorMembers.length > 0) {
        const authorIds = authorMembers.map((a) => a.author_id);
        const authorMenus = await prisma.authorMenu.findMany({
          where: { author_id: { in: authorIds } },
          select: { menu_id: true },
        });
        userMenuIds = new Set(authorMenus.map((m) => m.menu_id));

        // 권한 enum 기반 시스템 메뉴 자동 추가 (TN_AuthorMenu 부여 불요)
        for (const aid of authorIds) {
          for (const menuId of AUTO_SYSTEM_MENUS_BY_AUTHOR[aid] ?? []) {
            userMenuIds.add(menuId);
          }
        }
      }
    }

    // 워크스페이스별 메뉴 (구매/부여된 기능). 시스템 메뉴(msys*)는 워크스페이스 매핑 무관 — 권한만으로 노출 결정.
    let workspaceMenuIds: Set<string> = new Set();
    if (!isSysAdmin) {
      const workspaceId = session.user.workspaceId;
      if (workspaceId) {
        const workspaceMenus = await prisma.workspaceMenu.findMany({
          where: { workspace_id: workspaceId },
          select: { menu_id: true },
        });
        workspaceMenuIds = new Set(workspaceMenus.map((m) => m.menu_id));
      }
    }

    const rows = await prisma.menu.findMany({
      where: { use_at: "Y" },
      orderBy: [{ menu_level: "asc" }, { sort_ordr: "asc" }],
    });

    const navItems: NavItem[] = [];
    const parents = rows.filter((r) => r.menu_level === 1);

    // 일반 사용자: 권한 메뉴 ∩ 워크스페이스 메뉴. 시스템 메뉴(msys*)는 권한만으로 결정 (워크스페이스 매핑 우회).
    const isVisible = (menuId: string) => {
      if (isSysAdmin) return true;
      if (!userMenuIds.has(menuId)) return false;
      if (isProtectedMenu(menuId)) return true;
      return workspaceMenuIds.has(menuId);
    };

    for (const parent of parents) {
      const children = rows.filter((r) => r.menu_level === 2 && r.upper_menu_id === parent.menu_id);
      const subItems = children
        .filter((child) => isVisible(child.menu_id))
        .map((child) => ({
          id: child.menu_id,
          text: child.menu_nm,
          icon: child.icon || "doc",
          path: child.url ? `/${child.url}` : undefined,
        }));

      if (subItems.length > 0) {
        navItems.push({
          id: parent.menu_id,
          text: parent.menu_nm,
          icon: parent.icon || "folder",
          items: subItems,
        });
      }
    }

    return createSuccessResponse({ items: navItems });
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
