// app/api/external/devactivity/scheduler/[scheduler_id]/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.DEV_ACTIVITY_SERVICE_URL + "/scheduler";

// [GET] 단건 조회 핸들러
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}`, {
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

// [PUT] 수정 핸들러
const putHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "PUT";

  try {
    const body = await req.json();
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}`, {
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

// [DELETE] 삭제 핸들러
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "DELETE";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}`, {
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

// 스케줄러 관리 화면(mbiz1005) 단건 CRUD — operator 접근 업무 화면이라 가드를 화면 권한과 정렬 (#203).
export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });
export const PUT = withAuth(putHandler, { requireOperatorOrAdmin: true });
export const DELETE = withAuth(deleteHandler, { requireOperatorOrAdmin: true });
