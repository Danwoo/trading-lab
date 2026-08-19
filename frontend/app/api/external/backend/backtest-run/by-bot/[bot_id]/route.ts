// app/api/external/backend/backtest-run/by-bot/[bot_id]/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BACKEND_SERVICE_URL + "/backtest-run";

// [GET] 한 봇의 검증 이력 — 봇 화면이 「만들고 → 검증하고」의 가운데를 잇는 근거
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const limit = req.nextUrl.searchParams.get("limit");
    const query = limit ? `?limit=${encodeURIComponent(limit)}` : "";
    const result = await proxyApiRequest(`${BACKEND_URL}/by-bot/${encodeURIComponent(params.bot_id)}${query}`, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
