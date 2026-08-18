// app/api/external/backend/backtest-run/grid/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// backend prefix "/backtest-run" 을 byte-identical 로 복제한다 (backend 가 SoT — 경로 변경 시 lockstep)
const BACKEND_URL = env.BACKEND_SERVICE_URL + "/backtest-run";

// [POST] 격자 실행 — 실행이 곧 격자 실행이다 (스펙 D-Q1). 응답의 attempts_used 는 칸 수만큼 오른다
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const body = await req.json();
    const result = await proxyApiRequest(`${BACKEND_URL}/grid`, {
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
