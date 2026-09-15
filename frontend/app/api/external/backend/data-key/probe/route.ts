// app/api/external/backend/data-key/probe/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const BACKEND_URL = env.BACKEND_SERVICE_URL + "/data-key/probe";

// [POST] 넣으려는 값으로 소스에 한 번 물어본다 — 저장 전에 확인할 수 있게
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";

  try {
    const result = await proxyApiRequest(BACKEND_URL, {
      method: operation,
      headers: { Authorization: `Bearer ${session.accessToken}` },
      data: await req.json(),
    });

    // **확인은 등록이 아니다.** operation 을 넘기면 POST 표의 성공 문구(「등록이 완료되었습니다」)와
    // 201 이 붙어, 키가 틀렸다고 답한 확인(`ok:false`)까지 「저장됐다」로 읽힌다 (#445 B-17).
    // 만든 것이 없으므로 200 으로, 붙일 말이 없으므로 결과만 그대로 돌려준다.
    return createSuccessResponse(result);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler);
