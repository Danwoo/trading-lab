// app/api/common/system/adminuser/[email]/cascade/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { countUserCascade } from "@/lib/auth/authUtils";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

/**
 * [GET] /api/system/adminuser/[email]/cascade
 * 이 사용자를 지우면 함께 지워지는 것의 건수 — 삭제 확인 창(#356)이 삭제 직전에 읽는다.
 * 인가 옵션은 같은 경로의 DELETE 와 같다 — 지울 수 없는 대상은 세지도 못해야 한다.
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { email } = params;

  try {
    const counts = await countUserCascade(email);
    if (!counts) return createErrorResponse({ message: "사용자를 찾을 수 없습니다." }, operation);
    return createSuccessResponse(counts);
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, {
  scopeEmailParam: "email",
  protectSysAdminTarget: true,
  requireOperatorOrAdmin: true,
});
