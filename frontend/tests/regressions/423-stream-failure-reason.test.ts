// #423 — **스트리밍 대화가 이미 받은 실패 원인을 「잠시 후 다시 시도」로 덮어쓰지 않는다.**
//
// 배경: 봇 대화(:8011)·리서치 챗(:8003)이 안 떠 있을 때 프록시는 「연결 자체가 안 됐다」를 알고
// 있는데, 그 사실이 봉투를 못 건너 화면에는 5xx 일반 문구(「서버에서 오류가 발생했습니다. 잠시
// 후 다시 시도해 주세요.」)만 남았다. **다시 시도해도 안 된다** — 처방은 서비스 기동이다.
//
// 고친 방식은 새 것이 아니라 #342 의 **사유 코드**를 스트리밍 표면으로 넓힌 것이다: 봉투를
// 건너는 것은 닫힌 집합(`STREAM_FAILURE_CODES`)의 코드뿐이고, 문구는 클라이언트가 자기 언어
// 표에서 고른다. 그래서 내부 호스트·포트·스택이 화면에 실릴 자리가 없다.
//
// 이 파일이 잠그는 것 셋:
//   ① **전수** — 사유 갈래가 하나도 빠짐없이 상태·ko/en 문구를 갖는다.
//   ② **런타임** — 실제 라우트 핸들러가 연결 실패를 사유 코드로 옮기고, 그것이
//      `getApiErrorMessage` 를 거쳐 「기동하라」로 화면에 닿는다(일반 문구로 안 뭉개진다).
//   ③ **정적 · fail-closed** — `app/api/external/**` 의 SSE 프록시 라우트 **전부**가 그 분류를
//      지난다. 대상이 0건이면 실패한다 — 새 스트리밍 라우트가 조용히 옛 경로로 생기지 않게.
//
// **검증 경계** — 실제 :8011·:8003 을 띄우지 않는다. 세우는 것은 `fetch` 가 연결 실패로 던지는
// 모양(undici `TypeError: fetch failed` + `cause.code = ECONNREFUSED`)이고, 보는 것은 라우트가
// 만든 응답 본문·상태와 그것을 화면 문구로 옮긴 결과다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const EXTERNAL_API_ROOT = path.join(FRONTEND_ROOT, "app/api/external");

// 응답에 실리면 안 되는 것 — 실제 설정 대신 눈에 띄는 카나리를 넣는다.
const BOT_AGENT_HOST = "http://bot-agent.internal-canary.test:18011";
const MULTI_AGENT_HOST = "http://multi-agent.internal-canary.test:18003";

vi.mock("@/env", () => ({
  env: {
    BOT_AGENT_SERVICE_URL: BOT_AGENT_HOST,
    MULTI_AGENT_SERVICE_URL: MULTI_AGENT_HOST,
    APP_KEY: "canary-app",
    NODE_ENV: "development",
  },
}));

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: {
          user: { id: "u1", email: "operator@example.com" },
          session: { authorId: "operator", workspaceId: 1 },
        },
        headers: new Headers(),
      })),
    },
  },
}));

vi.mock("@/lib/auth/accountContext", () => ({
  resolveAccountContext: vi.fn(async () => ({ block: null, authorId: "operator", workspaceId: 1 })),
}));

vi.mock("@/lib/auth/authUtils", () => ({
  assertSameWorkspaceOrSysAdmin: vi.fn(async () => null),
  assertTargetNotSysAdmin: vi.fn(async () => null),
  normalizeEmail: (e: string) => e,
}));

/** undici 의 `fetch` 가 연결 실패에서 실제로 던지는 모양 — 원인은 `cause` 에 실린다. */
function connectionRefused(target: string): TypeError {
  const cause = Object.assign(new Error(`connect ECONNREFUSED ${target}`), {
    code: "ECONNREFUSED",
    syscall: "connect",
  });
  return Object.assign(new TypeError("fetch failed"), { cause });
}

/** 서버 응답을 axios 가 만드는 모양으로 옮긴다 — 화면이 실제로 받는 것이 이것이다. */
function asAxiosError(status: number, data: unknown) {
  return { message: `Request failed with status code ${status}`, response: { status, data } };
}

type StreamRoute = {
  label: string;
  module: string;
  expectedCode: string;
  /** 내부 호스트 — 응답 본문에 실리면 안 된다. */
  upstream: string;
};

/** 화면이 실제로 스트리밍을 태우는 두 라우트. */
const ROUTES: StreamRoute[] = [
  {
    label: "봇 대화 (:8011)",
    module: "@/app/api/external/bot-agent/bot-agent/route",
    expectedCode: "botAgent.service_unreachable",
    upstream: BOT_AGENT_HOST,
  },
  {
    label: "리서치 챗 (:8003)",
    module: "@/app/api/external/multi-agent/agent/example-ai/route",
    expectedCode: "research.service_unreachable",
    upstream: MULTI_AGENT_HOST,
  },
];

async function postWhileDown(route: StreamRoute) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw connectionRefused("127.0.0.1:18011");
    }),
  );
  vi.resetModules();
  const { POST } = (await import(route.module)) as { POST: (req: NextRequest, props?: any) => Promise<Response> };
  const response = await POST(
    new NextRequest("http://localhost/api/external/x", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: "눌림목 봇 만들어줘", gid: 1, question: "목표주가 근거" }),
    }),
    {},
  );
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

/** `app/api/external/**` 의 route.ts 전부. */
function listRouteFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listRouteFiles(full));
    else if (entry.isFile() && entry.name === "route.ts") out.push(full);
  }
  return out;
}

describe("#423 스트리밍 실패 사유", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("사유 갈래 전부에 ko/en 문구가 있고, HTTP 상태표는 실제로 봉투를 내는 갈래만 담는다", async () => {
    const { STREAM_FAILURE_CODES, STREAM_FAILURE_HTTP_STATUS, isStreamFailureCode } =
      await import("@/utils/common/errors/streamFailure");
    const { STREAM_FAILURE_MESSAGES: KO } = await import("@/utils/common/locale/ko/apierrors");
    const { STREAM_FAILURE_MESSAGES: EN } = await import("@/utils/common/locale/en/apierrors");

    expect(STREAM_FAILURE_CODES.length).toBeGreaterThan(0);
    for (const code of STREAM_FAILURE_CODES) {
      expect(KO[code], `ko ${code}`).toBeTruthy();
      expect(EN[code], `en ${code}`).toBeTruthy();
    }

    // 상태표는 **HTTP 봉투로 발행되는** 갈래만 담는다. 스트림이 열린 뒤 정해지는 사유
    // (`invalid_api_key`·`turn_failed`)는 200 안의 error 이벤트로만 나가므로 상태가 없다 —
    // 그것을 표에 남기면 없는 경로를 있다고 읽게 된다.
    const withStatus = Object.keys(STREAM_FAILURE_HTTP_STATUS);
    expect(withStatus.length, "상태표가 비었다 — 대조가 죽었다").toBeGreaterThan(0);
    for (const code of withStatus) {
      expect(isStreamFailureCode(code), `${code} 가 닫힌 집합 밖이다`).toBe(true);
    }
    expect(new Set(withStatus)).toEqual(new Set(ROUTES.map((route) => route.expectedCode)));

    console.info(
      `[#423] 사유 갈래 ${STREAM_FAILURE_CODES.length}건 — ko·en 확인, 그중 HTTP 봉투 ${withStatus.length}건`,
    );
  });

  it("서비스가 안 떠 있으면 화면이 「기동하라」고 말한다 — 재시도를 시키지 않는다", async () => {
    // 사유 코드가 없을 때 그 상태에서 나오는 일반 문구 — 갈래가 여기로 뭉개지면 안 된다.
    const generic = new Set([500, 502, 503, 504].map((s) => getApiErrorMessage(asAxiosError(s, {}))));

    for (const route of ROUTES) {
      const { status, body } = await postWhileDown(route);

      expect(body.code, `${route.label} body.code`).toBe(route.expectedCode);

      const message = getApiErrorMessage(asAxiosError(status, body));
      expect(generic.has(message), `${route.label} 가 일반 상태 문구로 뭉개졌다`).toBe(false);
      // 처방이 「재시도」가 아니라 「기동」이어야 한다.
      expect(message, `${route.label} 문구`).toMatch(/띄운 뒤|기동/);

      console.info(`[#423] ${route.label.padEnd(18)} HTTP ${status}  화면: ${JSON.stringify(message)}`);
    }
  });

  it("응답 본문에 내부 호스트·스택이 실리지 않는다", async () => {
    for (const route of ROUTES) {
      const { body } = await postWhileDown(route);
      const wire = JSON.stringify(body);

      expect(wire, `${route.label} 봉투에 내부 호스트가 실렸다`).not.toContain("internal-canary.test");
      expect(wire, `${route.label} 봉투에 업스트림 URL 이 실렸다`).not.toContain(route.upstream);
      expect(wire).not.toContain("ECONNREFUSED");
      expect(wire).not.toMatch(/\bat\s+\w+\s*\(/); // 스택 프레임 모양
    }
  });

  it("SSE 프록시 라우트 전부가 연결 실패를 사유 코드로 옮긴다 (0건이면 실패)", async () => {
    const streamRoutes = listRouteFiles(EXTERNAL_API_ROOT).filter((file) =>
      /"stream"/.test(fs.readFileSync(file, "utf8")),
    );

    expect(streamRoutes.length, "SSE 프록시 라우트를 0건 수집했다 — 그물이 죽었다").toBeGreaterThan(0);

    for (const file of streamRoutes) {
      const source = fs.readFileSync(file, "utf8");
      expect(source, `${path.relative(FRONTEND_ROOT, file)} 가 연결 실패를 분류하지 않는다`).toContain(
        "isUpstreamUnreachable",
      );
    }
    console.info(`[#423] SSE 프록시 라우트 ${streamRoutes.length}건 검사`);
  });
});
