// app/api/external/backend/data-key/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BACKEND_SERVICE_URL + "/data-key";

// [GET] 데이터 소스 키 상태 — 어디에 무엇을 넣어야 하는지. 값은 오지 않는다.
const getHandler = async (req: NextRequest, session: any) => {
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

// [PUT] 키를 그 서비스의 `.env` 에 쓴다 — 로컬 개발에서만 열린다(백엔드가 판정)
const putHandler = async (req: NextRequest, session: any) => {
  const operation = "PUT";

  try {
    const result = await proxyApiRequest(BACKEND_URL, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
      data: await req.json(),
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const PUT = withAuth(putHandler);
