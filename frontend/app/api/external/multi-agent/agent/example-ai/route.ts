// app/api/external/multi-agent/agent/example-ai/route.ts
// #160 슬라이스 D-나: 투자리서치 챗 프록시 (근거 카드를 싣는 example-ai 엔드포인트).
// /agent 프록시(route.ts)를 미러하되 backend path 만 /agent/example-ai.
// 룰13: backend path prefix "/agent"(agent_router.py APIRouter prefix) + 서브패스 "/example-ai".
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.MULTI_AGENT_SERVICE_URL + "/agent/example-ai";

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

// 리서치 챗 화면(mbiz1007)은 operator 접근 업무 화면 — 가드를 화면 권한과 정렬 (#202).
export const POST = withAuth(postHandler, { requireOperatorOrAdmin: true });
