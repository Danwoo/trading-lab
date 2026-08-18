// app/api/external/backend/backtest-run/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// backend prefix "/backtest-run" 을 byte-identical 로 복제한다 (backend 가 SoT — 경로 변경 시 lockstep)
const BACKEND_URL = env.BACKEND_SERVICE_URL + "/backtest-run";

// [POST] 단일 실행 — 격자의 한 칸을 계보에 이어 다시 볼 때 쓴다 (새 탐색은 /grid)
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const body = await req.json();
    const result = await proxyApiRequest(`${BACKEND_URL}`, {
      method: operation,
      data: body,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler);
