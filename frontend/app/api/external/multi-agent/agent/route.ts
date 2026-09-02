// app/api/external/multi-agent/agent/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createErrorResponse, createStreamFailureResponse } from "@/utils/common/api/responses";
import { isUpstreamUnreachable } from "@/utils/common/errors/streamFailure";

const BACKEND_URL = env.MULTI_AGENT_SERVICE_URL + "/agent";

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
    // 「연결 자체가 안 됐다」는 일반 5xx 로 보내면 화면이 「잠시 후 다시 시도」라고 말한다 —
    // 다시 시도해도 안 되고, 처방은 서비스 기동이다. 그 사실만 사유 코드로 건넨다 (#423).
    if (isUpstreamUnreachable(error)) return createStreamFailureResponse("research.service_unreachable");
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireSysAdmin: true });
