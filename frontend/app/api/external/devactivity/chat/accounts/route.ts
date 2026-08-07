// app/api/external/devactivity/chat/accounts/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.DEV_ACTIVITY_SERVICE_URL + "/chat/accounts";

// [GET] 최근 활동 계좌·포트폴리오 목록 (좌측 패널)
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

// 개발활동 조회 화면(mbiz1004) 좌측 목록 — operator 접근 업무 화면이라 가드를 화면 권한과 정렬 (#203).
export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
