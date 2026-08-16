// app/api/external/bot-agent/bot-agent/readiness/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BOT_AGENT_SERVICE_URL + "/bot-agent/readiness";

/** 대화를 걸 수 있는가 — 아니면 이유. 서비스가 안 떠 있는 경우도 화면이 이유로 다룬다. */
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

export const GET = withAuth(getHandler);
