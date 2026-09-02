// @vitest-environment node
//
// #445 B-17 — 「연결 확인」을 눌렀을 뿐인데 응답이 **등록**이라고 말했다:
//
//   [201] POST /api/external/backend/data-key/probe
//     RES: {"ok":false,"checked":true,"detail":"...","message":"등록이 완료되었습니다."}
//
// 확인은 아무것도 만들지 않는다. 백엔드 스키마(`DataKeyProbeOut`)에는 `message` 가 없다 —
// 붙인 것은 프록시의 `createSuccessResponse(result, "POST")` 이고, 그 표(`constants.ts`)의
// POST 성공 문구가 「등록이 완료되었습니다」이며 성공 상태가 201 이다.
//
// **키가 틀렸다고 답한 확인**(`ok:false`)에 「등록이 완료되었습니다」가 붙으면, 사용자는 키가
// 저장됐다고 읽는다. 실제로는 아무 일도 안 일어났다.
//
// `responses.ts` 가 Prisma 를 import 하므로 `npm run test:api-regressions` 로만 돈다.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/env", () => ({
  env: { NODE_ENV: "development", BACKEND_SERVICE_URL: "http://backend.test" },
}));
vi.mock("@/lib/auth/withAuth", () => ({
  withAuth: (handler: any) => (req: NextRequest) => handler(req, { accessToken: "t" }, {}),
}));
vi.mock("@/utils/common/api/server", () => ({ proxyApiRequest: vi.fn() }));

const { proxyApiRequest } = await import("@/utils/common/api/server");
const { POST } = await import("@/app/api/external/backend/data-key/probe/route");

const PROBE_RESULT = { ok: false, checked: true, detail: "data_go_kr: 소스가 자격을 거절했습니다 (HTTP 401)." };

function request() {
  return new NextRequest("http://localhost:3010/api/external/backend/data-key/probe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "data_go_kr", value: "NOT-A-REAL-KEY", setting: "MARKET_DATA_GOKR_SERVICE_KEY" }),
  });
}

describe("확인은 등록이라고 말하지 않는다", () => {
  beforeEach(() => {
    vi.mocked(proxyApiRequest).mockResolvedValue(PROBE_RESULT as never);
  });

  it("응답에 등록 문구가 없다", async () => {
    const body = await (await POST(request(), { params: Promise.resolve({}) })).json();

    expect(JSON.stringify(body)).not.toContain("등록이 완료");
    expect(body.message).toBeUndefined();
  });

  it("상태가 201 이 아니다 — 만든 것이 없다", async () => {
    expect((await POST(request(), { params: Promise.resolve({}) })).status).not.toBe(201);
  });

  it("확인 결과 자체는 그대로 넘어간다 — 사유가 사라지지 않는다", async () => {
    const body = await (await POST(request(), { params: Promise.resolve({}) })).json();

    expect(body.ok).toBe(false);
    expect(body.checked).toBe(true);
    expect(body.detail).toBe(PROBE_RESULT.detail);
  });

  it("통한 확인도 등록이라고 말하지 않는다", async () => {
    vi.mocked(proxyApiRequest).mockResolvedValue({ ok: true, checked: true, detail: "통했습니다." } as never);
    const body = await (await POST(request(), { params: Promise.resolve({}) })).json();

    expect(body.ok).toBe(true);
    expect(JSON.stringify(body)).not.toContain("등록");
  });
});
