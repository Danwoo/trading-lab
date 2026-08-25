// app/api/external/backend/chat/holders/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BACKEND_SERVICE_URL + "/chat/holders";

// [GET] 계좌주 필터 드롭다운용 목록
const getHandler = async (_req: NextRequest, session: any) => {
  const operation = "GET";
  try {
    const result = await proxyApiRequest(BACKEND_URL, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// 스케줄러 관리(mbiz1005) 화면의 계좌주 필터 — 가드를 화면 권한과 정렬 (#203).
export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
