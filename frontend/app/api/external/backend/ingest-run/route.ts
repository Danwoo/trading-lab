// app/api/external/backend/ingest-run/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

// backend prefix "/ingest-run" 을 byte-identical 로 복제한다 (backend 가 SoT — 경로 변경 시 lockstep)
const BACKEND_URL = env.BACKEND_SERVICE_URL + "/ingest-run";

// [GET] 적재 잡 이력 조회 — 요청·실행·이력이 같은 표다 (M2-AD-12)
const getHandler = async (req: NextRequest, session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const queryParams = Object.fromEntries(searchParams.entries());

    const result = await proxyApiRequest(`${BACKEND_URL}`, {
      method: operation,
      params: queryParams,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// [POST] 수동 적재 요청 — 큐에 넣고 즉시 반환한다. 실행은 백그라운드 워커가 집어 간다
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

export const GET = withAuth(getHandler);
export const POST = withAuth(postHandler);
