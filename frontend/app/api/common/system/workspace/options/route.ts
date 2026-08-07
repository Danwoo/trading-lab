// app/api/common/system/workspace/options/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [GET] /api/common/system/workspace/options
 * 활성 **공용** 워크스페이스 목록 (SelectBox 드롭다운용 - 페이지네이션 없음)
 * - 시스템관리자: 전체 공용 워크스페이스
 * - 운영자: 자기 워크스페이스만 (다른 워크스페이스명 노출 방지)
 *
 * 개인 워크스페이스는 소유자 1명의 것이라 "사용자를 배정할 곳"이 아니다 — 드롭다운에 실으면
 * 남의 개인 워크스페이스로 배정할 수 있게 되고, SaaS 에서는 가입자 수만큼 목록이 불어난다.
 */
const getHandler = async (_req: NextRequest, session: any) => {
  const operation = "GET";
  try {
    // 운영자는 어차피 자기 워크스페이스 한 줄만 보므로 is_personal 을 따지지 않는다 (이름 표시용).
    const where: any = session.user.isSysAdmin
      ? { use_at: "Y", is_personal: false }
      : { use_at: "Y", id: session.user.workspaceId ?? -1 };

    const items = await prisma.workspace.findMany({
      where,
      select: { id: true, workspace_code: true, workspace_nm: true },
      orderBy: { id: "asc" },
    });

    return createSuccessResponse({ items });
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
