// app/api/common/system/menu/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { isProtectedMenu } from "@/constants/protected";

/**
 * [GET] /api/system/menu
 * 메뉴 목록 조회
 * ?parent_options=true → 상위 메뉴 선택용 옵션(level 1,2)만 반환
 */
const getHandler = async (req: NextRequest, _session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const parentOptions = searchParams.get("parent_options");

    if (parentOptions === "true") {
      const rows = await prisma.menu.findMany({
        where: { menu_level: 1 },
        select: { menu_id: true, menu_nm: true, use_at: true },
        orderBy: { menu_id: "asc" },
      });
      return createSuccessResponse({
        data: rows.map((r) => ({ value: r.menu_id, label: r.menu_nm, use_at: r.use_at })),
      });
    }

    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    const where = convertFilterToPrismaWhere(filter);
    // 사용자 sort 가 있으면 그대로, 없으면 후처리로 트리 순서 (부모 → 자식, 각 그룹 sort_ordr asc)
    const explicitSort = convertSortToPrismaOrderBy(sort);
    const orderBy = explicitSort || [{ sort_ordr: "asc" }];

    const [menus, allMenus, total_count] = await Promise.all([
      prisma.menu.findMany({
        take,
        skip,
        where,
        orderBy,
        include: { author_menus: { select: { author: { select: { author_nm: true } } } } },
      }),
      prisma.menu.findMany({ select: { menu_id: true, menu_nm: true } }),
      prisma.menu.count({ where }),
    ]);

    // 사용자 정렬이 없을 때만 트리 순서 강제 (부모 바로 아래에 자식들)
    if (!explicitSort) {
      const parents = menus.filter((m) => m.menu_level === 1).sort((a, b) => (a.sort_ordr ?? 0) - (b.sort_ordr ?? 0));
      const childrenByParent = new Map<string, typeof menus>();
      for (const m of menus) {
        if (m.menu_level !== 1 && m.upper_menu_id) {
          const arr = childrenByParent.get(m.upper_menu_id) ?? [];
          arr.push(m);
          childrenByParent.set(m.upper_menu_id, arr);
        }
      }
      const sorted: typeof menus = [];
      for (const p of parents) {
        sorted.push(p);
        const children = (childrenByParent.get(p.menu_id) ?? []).sort(
          (a, b) => (a.sort_ordr ?? 0) - (b.sort_ordr ?? 0),
        );
        sorted.push(...children);
      }
      // 고아 메뉴 (부모 없는 2레벨) 끝에 부착
      const placedIds = new Set(sorted.map((m) => m.menu_id));
      for (const m of menus) if (!placedIds.has(m.menu_id)) sorted.push(m);
      menus.splice(0, menus.length, ...sorted);
    }

    const menuMap = new Map(allMenus.map((m) => [m.menu_id, m]));

    const items = menus.map((item, index) => {
      const parent = item.upper_menu_id ? menuMap.get(item.upper_menu_id) : null;
      const ParentGroup = parent?.menu_nm ?? "";
      const author_nm = item.author_menus.map((m) => m.author.author_nm).join(", ");
      return {
        ...item,
        author_menus: undefined,
        ParentGroup,
        author_nm,
        rn: (skip || 0) + index + 1,
        is_protected: isProtectedMenu(item.menu_id),
      };
    });

    return createSuccessResponse({ items, total_count });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [POST] /api/system/menu
 * 메뉴 생성
 */
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const data = await req.json();

    const menu_id = String(data.menu_id ?? "")
      .replace(/\s/g, "")
      .toLowerCase();

    const existing = await prisma.menu.findUnique({ where: { menu_id }, select: { menu_id: true } });
    if (existing) {
      return createErrorResponse({ message: `이미 사용 중인 메뉴 ID입니다. (${menu_id})` }, operation);
    }

    const menu = await prisma.menu.create({
      data: {
        menu_id,
        menu_nm: data.menu_nm,
        upper_menu_id: data.upper_menu_id || null,
        menu_level: data.menu_level,
        sort_ordr: data.sort_ordr,
        url: data.url || null,
        use_at: data.use_at,
        icon: data.icon || null,
        reg_id: session.user.email,
        reg_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "메뉴가 생성되었습니다.", data: menu });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
