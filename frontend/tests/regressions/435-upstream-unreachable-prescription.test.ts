// @vitest-environment node
//
// #435 (B-3) — 포트가 틀렸을 때 화면이 **「네트워크 연결을 확인해주세요」**라고 말했다.
//
// 사용자의 네트워크는 멀쩡하다. 끊긴 것은 **이 앱이 자기 설정으로 부른 주소**다.
// 사용자를 자기 공유기 쪽으로 보내는 오진이고, 그쪽을 아무리 고쳐도 안 된다.
//
// 뿌리는 `createErrorResponse` 의 axios 분기다 — `error.response` 가 없다는 것은 **연결 자체가
// 안 됐다**는 뜻인데, 그 사실을 버리고 작업별 일반 문구(「조회 중 오류가 발생했습니다」)로
// 뭉갰다. 그러면 클라이언트가 분류할 근거가 없어 마지막 폴백(`FALLBACK.network`)으로 떨어진다.
//
// 서버는 아는 것을 말해야 한다: **부른 서비스가 응답하지 않았다.** 주소 자체는 싣지 않는다 —
// 내부 호스트·포트는 화면에 낼 것이 아니다.
//
// `responses.ts` 가 Prisma 를 import 하므로 `npm run test:api-regressions` 로만 돈다.
import { describe, expect, it } from "vitest";
import { AxiosError, AxiosHeaders } from "axios";

import { createErrorResponse } from "@/utils/common/api/responses";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { STATUS_MESSAGES } from "@/utils/common/locale/ko/apierrors";

async function bodyOf(res: Response) {
  return (await res.json()) as { detail?: { msg?: string; type?: string }[]; message?: string };
}

function unreachable() {
  // 연결이 안 된 axios 오류는 `response` 가 없다 — 이것이 「서버가 답했다」와 갈리는 지점이다.
  const err = new AxiosError("connect ECONNREFUSED 127.0.0.1:8100", "ECONNREFUSED");
  err.config = { headers: new AxiosHeaders() } as never;
  return err;
}

/**
 * 응답을 **클라이언트가 받는 모양**으로 되돌린다 — 봉투를 만드는 쪽과 문구를 고르는 쪽 사이의
 * 이음매를 실제로 건넌다. 봉투만 단언하면 그 이음매에서 문구가 버려져도 초록으로 남는다.
 */
async function asClientError(res: Response) {
  return { response: { status: res.status, data: await res.json() } };
}

function answered(status: number) {
  const err = new AxiosError("Request failed", "ERR_BAD_REQUEST");
  err.config = { headers: new AxiosHeaders() } as never;
  err.response = { status, data: { detail: "백엔드가 준 사유" }, statusText: "", headers: {}, config: err.config };
  return err;
}

describe("연결이 안 된 것을 사용자 네트워크 탓으로 돌리지 않는다", () => {
  it("응답이 없는 axios 오류는 서비스가 응답하지 않았다고 말한다", async () => {
    const res = createErrorResponse(unreachable(), "GET");
    const body = await bodyOf(res);
    const msg = body.detail?.[0]?.msg ?? body.message ?? "";

    expect(msg).toMatch(/서비스/);
    expect(msg).not.toMatch(/네트워크 연결을 확인/);
  });

  it("처방이 사용자가 확인할 수 있는 것을 가리킨다 — 주소·서비스 상태", async () => {
    const body = await bodyOf(createErrorResponse(unreachable(), "GET"));
    const msg = body.detail?.[0]?.msg ?? "";

    expect(msg).toMatch(/주소|포트|떠 있는지/);
  });

  it("내부 호스트·포트를 화면 문구에 싣지 않는다", async () => {
    const body = await bodyOf(createErrorResponse(unreachable(), "GET"));
    const msg = body.detail?.[0]?.msg ?? "";

    expect(msg).not.toMatch(/127\.0\.0\.1|localhost|:\d{4}|ECONNREFUSED/);
  });

  it("상태가 503 인 것은 그대로다 — 부른 쪽이 아니라 부름받은 쪽의 문제다", async () => {
    expect(createErrorResponse(unreachable(), "GET").status).toBe(503);
  });

  it("화면에 실제로 뜨는 문구가 서비스 상태·주소를 가리킨다", async () => {
    const shown = getApiErrorMessage(await asClientError(createErrorResponse(unreachable(), "GET")));

    expect(shown).toMatch(/떠 있는지|주소|포트/);
    expect(shown).not.toBe(STATUS_MESSAGES[503]);
    expect(shown).not.toMatch(/네트워크 연결을 확인/);
  });

  it("사유 코드가 빠지면 5xx 차단이 문구를 삼킨다 — 이 그물이 지키는 것이 그 코드다", async () => {
    const res = createErrorResponse(unreachable(), "GET");
    const { response } = await asClientError(res);
    const { code: _dropped, ...withoutCode } = response.data as { code?: string };

    expect(getApiErrorMessage({ response: { status: response.status, data: withoutCode } })).toBe(STATUS_MESSAGES[503]);
  });

  it("화면 문구에도 내부 호스트·포트가 실리지 않는다", async () => {
    const shown = getApiErrorMessage(await asClientError(createErrorResponse(unreachable(), "GET")));

    expect(shown).not.toMatch(/127\.0\.0\.1|localhost|:\d{4}|ECONNREFUSED/);
  });

  it("서버가 답한 오류는 종전대로 그 사유를 그대로 넘긴다 — 막는 범위가 넓어지지 않았다", async () => {
    const res = createErrorResponse(answered(422), "POST");
    expect(res.status).toBe(422);
    expect(await bodyOf(res)).toEqual({ detail: "백엔드가 준 사유" });
  });
});
