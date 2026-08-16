// app/api/external/bot-agent/bot-agent/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BOT_AGENT_SERVICE_URL + "/bot-agent";

/** 봇 만들기 대화 한 턴 — SSE 를 그대로 흘린다(`stream`). */
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";
  try {
    const body = await req.json();
    return await proxyApiRequest(
      BACKEND_URL,
      {
        method: operation,
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      },
      "stream",
    );
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler);
