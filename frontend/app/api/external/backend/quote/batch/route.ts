// app/api/external/backend/quote/batch/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// backend prefix "/quote/batch" 를 byte-identical 로 복제한다 (backend 가 SoT — 경로 변경 시 lockstep)
const BACKEND_URL = env.BACKEND_SERVICE_URL + "/quote/batch";

// [POST] 일괄 시세 조회 (갈래 3)
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
