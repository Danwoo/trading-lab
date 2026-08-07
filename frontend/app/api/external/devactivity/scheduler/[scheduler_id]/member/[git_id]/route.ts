// app/api/external/devactivity/scheduler/[scheduler_id]/member/[git_id]/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.DEV_ACTIVITY_SERVICE_URL + "/scheduler";

// [DELETE] 멤버 제거 핸들러
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "DELETE";

  try {
    const result = await proxyApiRequest(
      `${BACKEND_URL}/${encodeURIComponent(params.scheduler_id)}/member/${encodeURIComponent(params.git_id)}`,
      {
        method: operation,
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      },
    );

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// 스케줄러 관리 화면(mbiz1005) 멤버 제거 — operator 접근 업무 화면이라 가드를 화면 권한과 정렬 (#203).
export const DELETE = withAuth(deleteHandler, { requireOperatorOrAdmin: true });
