// app/api/common/system/menu/[menu_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { isProtectedMenu } from "@/constants/protected";
import { MenuUpdateInSchema } from "@/schemas/common/menu";

/**
 * [GET] /api/system/menu/[menu_id]
 * 메뉴 상세 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { menu_id } = params;

  try {
    const menu = await prisma.menu.findUnique({ where: { menu_id } });

    if (!menu) {
      return createErrorResponse({ message: "메뉴를 찾을 수 없습니다." }, operation);
    }

    const parent = menu.upper_menu_id
      ? await prisma.menu.findUnique({ where: { menu_id: menu.upper_menu_id }, select: { menu_nm: true } })
      : null;

    return createSuccessResponse({
      ...menu,
      ParentGroup: parent?.menu_nm ?? "",
      is_protected: isProtectedMenu(menu_id),
    });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [PUT] /api/system/menu/[menu_id]
 * 메뉴 수정
 *
 * **PUT = 전체 표현**이다 (#400, 계약 근거는 `adminuser/[email]/route.ts` 의 PUT 주석). 본문을
 * 클라이언트(`menuService.updateMenu`)와 **같은 스키마**(`MenuUpdateInSchema`)로 경계에서 파싱하고,
 * 필수 필드(`menu_nm`·`menu_level`·`sort_ordr`·`use_at`)가 빠지면 400 이다 — 예전엔 그 필드들이
 * Prisma `undefined`(생략=무시)로 흘러가는데 `upper_menu_id`·`url`·`icon` 만 생략=삭제라,
 * 한 update 안에서 계약이 갈렸다.
 */
const putHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "PUT";
  const { menu_id } = params;

  try {
    // 본문 읽기를 try 안으로 넣는다 — 예전엔 try 밖이라 JSON 이 아닌 본문 하나가 그대로 500 이 됐다.
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return createErrorResponse({ message: "요청 본문을 읽을 수 없습니다." }, operation);
    }

    const parsed = MenuUpdateInSchema.safeParse(body);
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      return createErrorResponse(
        { message: `요청 본문이 올바르지 않습니다: ${issue.path.join(".") || "body"} — ${issue.message}` },
        operation,
      );
    }
    const data = parsed.data;

    if (isProtectedMenu(menu_id) && data.use_at === "N") {
      return createErrorResponse({ message: "시스템 메뉴는 미사용으로 변경할 수 없습니다." }, operation);
    }

    const menu = await prisma.menu.update({
      where: { menu_id },
      data: {
        // 전체 표현 — 선택 필드의 생략은 명시적 null 이다.
        menu_nm: data.menu_nm,
        upper_menu_id: data.upper_menu_id ?? null,
        menu_level: data.menu_level,
        sort_ordr: data.sort_ordr,
        url: data.url ?? null,
        use_at: data.use_at,
        icon: data.icon ?? null,
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    return createSuccessResponse({ message: "메뉴가 수정되었습니다.", data: menu });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const PUT = withAuth(putHandler, { requireSysAdmin: true });

/**
 * [DELETE] /api/system/menu/[menu_id]
 * 메뉴 삭제
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { menu_id } = params;

  try {
    if (isProtectedMenu(menu_id)) {
      return createErrorResponse({ message: "시스템 메뉴는 삭제할 수 없습니다." }, operation);
    }

    const childCount = await prisma.menu.count({ where: { upper_menu_id: menu_id } });
    if (childCount > 0) {
      return createErrorResponse({ message: "하위 메뉴가 존재하여 삭제할 수 없습니다." }, operation);
    }

    await prisma.$transaction([
      prisma.authorMenu.deleteMany({ where: { menu_id } }),
      prisma.menu.delete({ where: { menu_id } }),
    ]);

    return createSuccessResponse({ message: "메뉴가 삭제되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { requireSysAdmin: true });
