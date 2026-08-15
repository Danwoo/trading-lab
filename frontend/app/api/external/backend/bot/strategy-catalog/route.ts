// app/api/external/backend/bot/strategy-catalog/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// 정적 세그먼트라 같은 층의 `[botId]` 보다 먼저 잡힌다 (Next.js 라우팅 우선순위).
const BACKEND_URL = env.BACKEND_SERVICE_URL + "/bot/strategy-catalog";

// [GET] 전략 목록 — 전략 파일 선언에서 만들어진 폼 스키마
const getHandler = async (req: NextRequest, session: any) => {
  const operation = "GET";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}`, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
