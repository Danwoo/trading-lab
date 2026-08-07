// app/api/external/devactivity/chat/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.DEV_ACTIVITY_SERVICE_URL + "/chat";

// [POST] 질문 → 커밋 검색 → LLM 답변 SSE 스트리밍 (stream 모드 = Response 패스스루)
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

// 개발활동 조회 화면(mbiz1004)의 챗 — operator 접근 업무 화면이라 가드를 화면 권한과 정렬 (#203).
export const POST = withAuth(postHandler, { requireOperatorOrAdmin: true });
