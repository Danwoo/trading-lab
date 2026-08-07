// app/api/external/devactivity/scheduler/[scheduler_id]/member/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.DEV_ACTIVITY_SERVICE_URL + "/scheduler";

// [GET] 멤버 목록 조회 핸들러
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}/member`, {
      method: operation,
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// [POST] 멤버 추가 핸들러
const postHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "POST";

  try {
    const body = await req.json();
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}/member`, {
      method: operation,
      data: body,
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// 스케줄러 관리 화면(mbiz1005) 멤버 조회·추가 — operator 접근 업무 화면이라 가드를 화면 권한과 정렬 (#203).
export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
export const POST = withAuth(postHandler, { requireOperatorOrAdmin: true });
