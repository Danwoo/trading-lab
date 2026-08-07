// app/api/external/backend/research-document/[research_doc_id]/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BACKEND_SERVICE_URL + "/research-document";

// [GET] 리서치 문서 단건 조회 (색인 상태·chunk_count 포함)
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.research_doc_id)}`, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

// [DELETE] 리서치 문서 삭제 (색인·레코드 제거)
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "DELETE";

  try {
    const result = await proxyApiRequest(`${BACKEND_URL}/${encodeURIComponent(params.research_doc_id)}`, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });

    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const DELETE = withAuth(deleteHandler);
