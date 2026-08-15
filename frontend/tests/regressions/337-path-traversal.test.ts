// #337 4차 교차 리뷰 N1 — 「가장 중요한 축」(app/api/external/* 조립부 encodeURIComponent) 에
// 회귀 그물이 0건이었다는 지적에 대한 대응. 5차 교차 리뷰가 이 그물 자체의 구멍 세 개(주입
// A/B/C 로 실측)를 다시 잡아 아래 (1)(2) 를 고쳤다 — 각 지적과 대응은 해당 위치에 인라인으로 남긴다.
//
// 리뷰어가 실측으로 증명한 것: `portfolio/[portfolio_id]/route.ts` 의 encodeURIComponent 3곳만
// 지우고 `vitest run`·`tsc --noEmit`·`eslint .` 를 돌리면 32 files/303 tests 전부 초록이었다.
// 안전이 옮겨간 축(호출부 인코딩)을 실제로 실행해 보는 테스트가 하나도 없었기 때문이다.
//
// 이 파일은 두 층으로 그 축을 덮는다.
//
// (1) 정적 net(아래 첫 describe) — `app/api/external/**` 전체를 스캔해 params 가
//     **encodeURIComponent 없이** URL 템플릿에 꽂히는 자리가 있는지 본다. `${params.x}` 형태뿐
//     아니라 `${params["x"]}`/`${params['x']}`, 그리고 그 라우트 폴더명([x])에서 뽑은 이름으로
//     구조분해된 맨몸 `${x}` 까지 본다(5차 리뷰 주입 C — 구조분해 리팩터로 인코딩이 빠진 경우가
//     이전 정규식 `/\$\{(?!encodeURIComponent\()params\.\w+\}/g` 를 그대로 통과했다).
//     **정직한 한계**: 이 규칙도 완전하지 않다 — encodeURIComponent 결과를 중간 변수에 담아 이름을
//     또 바꾸는 형태(`const t = encodeURIComponent(params.x); ...` 뒤 다른 이름으로 재대입),
//     문자열 `+` 연결, `params` 자체를 통째로 스프레드하는 형태는 정규식으로 못 잡는다. 그 틈은
//     (2) 런타임 net 이 메운다 — 소스 형태와 무관하게 **실제 핸들러가 만드는 URL 을 검사**하므로
//     정적 net 이 놓친 형태도 거기서 잡힌다. 그래서 이 정적 net 은 "빠른 1차 경보"로만 쓴다(주장
//     낮춤 — 5차 리뷰 지적①②).
//
// (2) 런타임 net(두 번째 describe) — 실제 라우트 핸들러(`withAuth` 로 감싼 GET/PUT/POST/DELETE)를
//     **직접 호출**해, ① B1 페이로드(원문 `/` 를 포함한 디코딩 값)가 `proxyApiRequest` 호출 전에
//     차단되는지, ② 정상 값은 여전히 올바르게 인코딩되어 백엔드로 나가는지를 본다. 소스 코드의
//     조립 형태(destructure·중간변수 등)와 무관하게 **핸들러가 실제로 만든 URL 문자열**을 비교하므로
//     이 축에서는 "20개 호출부 전부 검사" 주장이 형태에 의존하지 않는다 — 단, 그 비교가 유효하려면
//     인코딩 전후가 실제로 달라지는 값을 써야 한다. 5차 리뷰가 `ticker: "BRK.B"` 는
//     `encodeURIComponent("BRK.B") === "BRK.B"` 라 6개 호출부(ticker 축)에서 이 비교가 공회전한다고
//     지적해 아래 `rawValues.ticker` 를 바꿨다.
//     `app/api/external/**` 의 호출부 전부(9파일, PR #337 본문·리뷰 전수 대조)를 표로 검사한다 —
//     검사 대상이 0건이면 실패한다(이 레포의 fail-closed 원칙, #252 계열). 표의 콜사이트 수는
//     `listRouteFiles` 실측과 대조해 드리프트를 잡는다(아래 `EXPECTED_CALL_SITE_COUNT`).
//
// 무거운 의존성(better-auth, 실제 env 검증, DB 접속) 은 mock 해서 순수하게 라우트 조립 로직만
// 검증한다 — `@/env`·`@/lib/auth/auth`·`@/lib/auth/authUtils`·`next/headers` 를 얇게 mock.
// 단, 생성된 Prisma 클라이언트(`@/prisma/generated/client`)는 mock 하지 않는다 — `withAuth` →
// `utils/common/api/responses.ts` 가 이 라우트 핸들러들이 실제로 통과하는 에러 응답 경로(B1
// 차단의 400 도 이 경로)에서 그 타입을 쓰기 때문에, mock 하면 "실제 핸들러가 400 을 반환한다"는
// 이 그물의 핵심 단정이 mock 의 재현이 되어버린다(약해짐). 그래서 이 파일은 기본 `npm test`
// (vitest.config.ts, `npm ci --ignore-scripts` 로 도는 CI frontend-unit 잡)에서 빼고
// `npm run test:api-regressions`(vitest.api-regressions.config.ts, CI frontend-api-regressions
// 잡이 먼저 `npx prisma generate` 를 돌림)로만 돈다 — #337 CI 결함: 기본 잡 안에 있을 때
// 로컬(생성된 클라이언트가 이미 있음)은 초록이었지만 CI(클라이언트 없음)는
// `ERR_MODULE_NOT_FOUND` 로 빨강이었다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const EXTERNAL_API_ROOT = path.join(FRONTEND_ROOT, "app/api/external");

function listRouteFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listRouteFiles(full));
    else if (entry.isFile() && entry.name === "route.ts") out.push(full);
  }
  return out;
}

/**
 * 파일 경로의 동적 세그먼트 폴더명(`[xxx]`)에서 그 파일이 다룰 수 있는 params 키 이름을 뽑는다 —
 * Next.js 라우팅 규약상 그 파일 안에서 `params.xxx` 또는 그 이름으로 구조분해된 형태로만 나타날 수
 * 있다. 하드코딩 목록이 아니라 파일시스템에서 매번 다시 뽑으므로 라우트가 늘어도 따라간다.
 */
function extractDynamicSegmentNames(filePath: string): string[] {
  const rel = path.relative(EXTERNAL_API_ROOT, filePath);
  const names: string[] = [];
  for (const m of rel.matchAll(/\[(\w+)\]/g)) names.push(m[1]);
  return names;
}

type Interpolation = { raw: string; wrapped: boolean };

/**
 * 이 파일 안에서 params 값이 URL 템플릿 리터럴에 꽂히는 자리를 전부 찾는다 — `${params.x}`,
 * `${params["x"]}`/`${params['x']}`, 그리고 이 파일의 동적 세그먼트 이름으로 구조분해된 맨몸
 * `${x}` 까지(5차 리뷰 주입 C 대응). `encodeURIComponent(...)` 로 감싸였는지는 `wrapped` 로 판정한다.
 *
 * 한계는 파일 상단 주석 (1) 참조 — 이 함수는 정적 net 과 드리프트 카운트(아래 `EXPECTED_CALL_SITE_COUNT`)
 * 양쪽에서 공유한다.
 */
function scanInterpolations(filePath: string, src: string): Interpolation[] {
  const names = extractDynamicSegmentNames(filePath);
  const escaped = names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const bareAlt = escaped.length > 0 ? `|${escaped.join("|")}` : "";
  const pattern = new RegExp(
    `\\$\\{(encodeURIComponent\\()?(?:params\\.\\w+|params\\[["']\\w+["']\\]${bareAlt})\\)?\\}`,
    "g",
  );
  return [...src.matchAll(pattern)].map((m) => ({ raw: m[0], wrapped: Boolean(m[1]) }));
}

/**
 * 호출부(call site) 단위로 센다 — `CALL_SITES` 표는 URL 을 조립하는 템플릿 리터럴 하나당 한 행이다
 * (예: `portfolio_id`·`ticker` 두 축을 동시에 꽂는 `holding/[ticker]` 라우트도 표에는 method 당
 * 한 행). `scanInterpolations` 는 params 축(param) 단위로 세므로 2-param 콜사이트에서 표 행 수보다
 * 많이 나온다 — 그래서 드리프트 대조는 백틱 템플릿 리터럴 단위로 묶어서 센다: 그 리터럴 안에
 * 인터폴레이션이 하나라도 있으면 "콜사이트 1개"로 카운트한다. 이 파일에 백틱 문자열은 URL 조립
 * 아니면 `Authorization: \`Bearer ${session.accessToken}\`` 류뿐이라(params 미포함, 필터에서
 * 자동 제외) 오탐이 없다(9파일 전수 확인).
 */
function countCallSites(filePath: string, src: string): number {
  const templateLiterals = src.match(/`[^`]*`/g) ?? [];
  return templateLiterals.filter((lit) => scanInterpolations(filePath, lit).length > 0).length;
}

describe("정적 net — app/api/external 전체에서 params 가 encodeURIComponent 없이 URL에 꽂히는 자리 0건", () => {
  it("app/api/external 아래 route.ts 파일이 실제로 스캔됐다 (검사 대상 0건 방지)", () => {
    const files = listRouteFiles(EXTERNAL_API_ROOT);
    expect(files.length).toBeGreaterThan(0);
  });

  it('params 가 encodeURIComponent 로 감싸이지 않은 채 URL에 꽂히는 자리가 없다 (params.x · params["x"] · 구조분해된 맨몸 x)', () => {
    const files = listRouteFiles(EXTERNAL_API_ROOT);
    const hits: string[] = [];
    for (const file of files) {
      const src = fs.readFileSync(file, "utf-8");
      const unwrapped = scanInterpolations(file, src).filter((x) => !x.wrapped);
      if (unwrapped.length > 0) {
        hits.push(`${path.relative(FRONTEND_ROOT, file)}: ${unwrapped.map((x) => x.raw).join(", ")}`);
      }
    }
    expect(hits).toEqual([]);
  });
});

// ── 런타임 net ──────────────────────────────────────────────────────────
//
// vi.mock 호출은 파일 최상단에 리터럴로 둔다 — vitest 가 이 호출들을 정적으로 끌어올려 아래
// `await import(...)`(동적 import) 시점보다 먼저 등록되게 한다. 함수로 감싸면 이 정적 끌어올림이
// 적용되지 않는다.

vi.mock("@/env", () => ({
  env: {
    BACKEND_SERVICE_URL: "http://backend.test",
    DEV_ACTIVITY_SERVICE_URL: "http://devactivity.test",
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
          // GENERAL_ADMIN_AUTHOR_ID("operator") — requireOperatorOrAdmin 라우트도 통과시켜
          // 가드 도달 전에 403 으로 끊기지 않게 한다.
          session: { authorId: "operator", workspaceId: 1 },
        },
        headers: new Headers(),
      })),
    },
  },
}));

// scopeEmailParam 을 쓰는 라우트는 이 20개 호출부에 없다(portfolio·watchlist·research-document·
// scheduler 전부 미사용, app/api/external 소스 확인) — 그래도 withAuth.ts 가 정적 import 하므로
// 무거운 prisma 연쇄(authUtils → lib/prisma/client → 실 DB 어댑터 생성)를 막기 위해 mock 한다.
vi.mock("@/lib/auth/authUtils", () => ({
  assertSameWorkspaceOrSysAdmin: vi.fn(async () => null),
  assertTargetNotSysAdmin: vi.fn(async () => null),
  normalizeEmail: (e: string) => e,
}));

const proxyApiRequest = vi.fn(async (_url: string, _options?: unknown) => ({ ok: true }));
vi.mock("@/utils/common/api/server", () => ({ proxyApiRequest }));

type CallSite = {
  file: string;
  label: string;
  method: "GET" | "PUT" | "POST" | "DELETE";
  opName: string;
  /** withAuth 옵션 — requireOperatorOrAdmin 라우트는 mock 세션이 operator 라 통과한다. */
  needsBody: boolean;
  /** 이 콜사이트가 실제로 조립하는 URL 세그먼트들 — encodeURIComponent 적용 여부 검증용. */
  buildUrl: (encodedParams: Record<string, string>) => string;
  /** 이 콜사이트가 받는 동적 세그먼트 params 전체(공격 대상 key 포함). */
  paramKeys: string[];
};

const BACKEND = "http://backend.test/portfolio";
const WATCHLIST = "http://backend.test/watchlist";
const DOC = "http://backend.test/research-document";
const SCHED = "http://devactivity.test/scheduler";
const BOT = "http://backend.test/bot";

// app/api/external/** 안에서 params 를 백엔드 URL 템플릿에 꽂는 자리 전부(services/common/* 는
// 브라우저→자체 API 호출이라 이 표 밖, N3 로 별도 처리). 건수는 손으로 적지 않는다 —
// `EXPECTED_CALL_SITE_COUNT` 가 파일시스템을 실측해 이 표와 대조한다.
const CALL_SITES: CallSite[] = [
  // 봇 — #150 B1. `bot/route` 와 `bot/strategy-catalog/route` 는 params 를 URL 에 안 꽂아
  // 콜사이트가 아니다(정적 카운트에도 안 잡힌다).
  ...(["GET", "PUT", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/backend/bot/[botId]/route",
    label: `bot/[botId] ${method}`,
    method,
    opName: method,
    needsBody: method === "PUT",
    paramKeys: ["botId"],
    buildUrl: (p: Record<string, string>) => `${BOT}/${p.botId}`,
  })),
  ...(["GET", "PUT", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/backend/portfolio/[portfolio_id]/route",
    label: `portfolio/[portfolio_id] ${method}`,
    method,
    opName: method,
    needsBody: method === "PUT",
    paramKeys: ["portfolio_id"],
    buildUrl: (p: Record<string, string>) => `${BACKEND}/${p.portfolio_id}`,
  })),
  ...(["GET", "POST"] as const).map((method) => ({
    file: "@/app/api/external/backend/portfolio/[portfolio_id]/holding/route",
    label: `portfolio/[portfolio_id]/holding ${method}`,
    method,
    opName: method,
    needsBody: method === "POST",
    paramKeys: ["portfolio_id"],
    buildUrl: (p: Record<string, string>) => `${BACKEND}/${p.portfolio_id}/holding`,
  })),
  ...(["GET", "PUT", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/backend/portfolio/[portfolio_id]/holding/[ticker]/route",
    label: `portfolio/[portfolio_id]/holding/[ticker] ${method}`,
    method,
    opName: method,
    needsBody: method === "PUT",
    paramKeys: ["portfolio_id", "ticker"],
    buildUrl: (p: Record<string, string>) => `${BACKEND}/${p.portfolio_id}/holding/${p.ticker}`,
  })),
  ...(["GET", "PUT", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/backend/watchlist/[ticker]/route",
    label: `watchlist/[ticker] ${method}`,
    method,
    opName: method,
    needsBody: method === "PUT",
    paramKeys: ["ticker"],
    buildUrl: (p: Record<string, string>) => `${WATCHLIST}/${p.ticker}`,
  })),
  ...(["GET", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/backend/research-document/[research_doc_id]/route",
    label: `research-document/[research_doc_id] ${method}`,
    method,
    opName: method,
    needsBody: false,
    paramKeys: ["research_doc_id"],
    buildUrl: (p: Record<string, string>) => `${DOC}/${p.research_doc_id}`,
  })),
  ...(["GET", "PUT", "DELETE"] as const).map((method) => ({
    file: "@/app/api/external/devactivity/scheduler/[scheduler_id]/route",
    label: `scheduler/[scheduler_id] ${method}`,
    method,
    opName: method,
    needsBody: method === "PUT",
    paramKeys: ["scheduler_id"],
    buildUrl: (p: Record<string, string>) => `${SCHED}/${p.scheduler_id}`,
  })),
  {
    file: "@/app/api/external/devactivity/scheduler/[scheduler_id]/run/route",
    label: "scheduler/[scheduler_id]/run POST",
    method: "POST",
    opName: "POST",
    needsBody: false,
    paramKeys: ["scheduler_id"],
    buildUrl: (p: Record<string, string>) => `${SCHED}/${p.scheduler_id}/run`,
  },
  ...(["GET", "POST"] as const).map((method) => ({
    file: "@/app/api/external/devactivity/scheduler/[scheduler_id]/member/route",
    label: `scheduler/[scheduler_id]/member ${method}`,
    method,
    opName: method,
    needsBody: method === "POST",
    paramKeys: ["scheduler_id"],
    buildUrl: (p: Record<string, string>) => `${SCHED}/${p.scheduler_id}/member`,
  })),
  {
    file: "@/app/api/external/devactivity/scheduler/[scheduler_id]/member/[git_id]/route",
    label: "scheduler/[scheduler_id]/member/[git_id] DELETE",
    method: "DELETE",
    opName: "DELETE",
    needsBody: false,
    paramKeys: ["scheduler_id", "git_id"],
    buildUrl: (p: Record<string, string>) => `${SCHED}/${p.scheduler_id}/member/${p.git_id}`,
  },
];

// `app/api/external/**` 를 listRouteFiles 로 실측한 호출부 수 — 5차 리뷰 지적③: 이전엔 손으로 쓴
// `CALL_SITES.length` 를 손으로 쓴 상수 20 과 비교했다(둘 다 표, 파일시스템을 세지 않음). 21번째
// 호출부가 생겨도 이 상수를 안 고치면 조용히 초록이었다. 지금은 이 값이 파일시스템 스캔 결과라,
// 아래 `EXPECTED_CALL_SITE_COUNT건 콜사이트 수 일치` 테스트가 `CALL_SITES` 표와 실제 소스를
// 대조한다 — 표를 안 고치고 새 호출부만 추가하면 이 값과 `CALL_SITES.length` 가 갈려 실패한다.
const EXPECTED_CALL_SITE_COUNT = listRouteFiles(EXTERNAL_API_ROOT).reduce(
  (sum, file) => sum + countCallSites(file, fs.readFileSync(file, "utf-8")),
  0,
);

async function loadHandler(file: string, method: CallSite["method"]) {
  const mod: any = await import(file);
  return mod[method] as (req: NextRequest, props: any) => Promise<Response>;
}

function makeRequest(method: string, needsBody: boolean): NextRequest {
  const init: any = { method };
  if (needsBody) {
    init.body = JSON.stringify({});
    init.headers = { "content-type": "application/json" };
  }
  return new NextRequest("http://localhost/x", init);
}

beforeEach(() => {
  proxyApiRequest.mockClear();
  proxyApiRequest.mockResolvedValue({ ok: true });
});

describe(`런타임 net — app/api/external 호출부 전수(${EXPECTED_CALL_SITE_COUNT}건) B1 차단·정상값 인코딩`, () => {
  it(`검사 대상이 0건이 아니고, 표에 담긴 콜사이트 수가 listRouteFiles 실측(${EXPECTED_CALL_SITE_COUNT}건)과 일치한다 (드리프트 방지)`, () => {
    expect(EXPECTED_CALL_SITE_COUNT).toBeGreaterThan(0);
    expect(CALL_SITES.length).toBe(EXPECTED_CALL_SITE_COUNT);
  });

  describe.each(CALL_SITES)("$label", (site) => {
    // 공격 대상 param 은 매번 하나씩 돌아가며 오염시키고, 나머지는 정상 값을 넣는다 — 2-param
    // 콜사이트(holding/[ticker], member/[git_id])도 두 축 모두 독립적으로 검사된다.
    it.each(site.paramKeys)(
      "%s 에 B1 페이로드('core/holding' 류 원문 '/')를 넣으면 프록시 호출 전에 차단된다",
      async (attackKey) => {
        const params: Record<string, string> = Object.fromEntries(site.paramKeys.map((k) => [k, "safe-value"]));
        params[attackKey] = "core/holding"; // 디코딩된 값 — Next 라우터가 %2F 를 이렇게 넘긴다(B1 재현)

        const handler = await loadHandler(site.file, site.method);
        const res = await handler(makeRequest(site.method, site.needsBody), { params: Promise.resolve(params) });

        expect(res.status).toBe(400);
        expect(proxyApiRequest).not.toHaveBeenCalled();
      },
    );

    it("한글·'@'·작은따옴표 값은 여전히 통과하고, 백엔드로 나가는 URL 이 정확히 encodeURIComponent 된 형태다", async () => {
      const rawValues: Record<string, string> = {
        portfolio_id: "성장주",
        // "BRK.B" 는 전부 encodeURIComponent 의 unreserved 문자(A-Za-z0-9-_.!~*'())라 인코딩해도
        // 값이 그대로다 — `encodeURIComponent("BRK.B") === "BRK.B"`. 그 값으로는 아래
        // `calledUrl === site.buildUrl(encodedParams)` 단정이 "인코딩을 했는지 안 했는지"를 구분하지
        // 못해, watchlist/[ticker] 3건 + holding/[ticker] 3건에서 인코딩 축이 공회전했다(5차 리뷰
        // 지적① — 주입 C 로 실측: encodeURIComponent 를 통째로 지워도 이 테스트가 초록이었다).
        // 인코딩 시 실제로 값이 바뀌는 값으로 바꾼다.
        ticker: "삼성전자",
        research_doc_id: "문서'1",
        scheduler_id: "일간수집",
        git_id: "user@example.com",
      };
      const params: Record<string, string> = Object.fromEntries(
        site.paramKeys.map((k) => [k, rawValues[k] ?? `값-${k}`]),
      );
      const encodedParams = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, encodeURIComponent(v)]));

      const handler = await loadHandler(site.file, site.method);
      const res = await handler(makeRequest(site.method, site.needsBody), { params: Promise.resolve(params) });

      expect(res.status).not.toBe(400);
      expect(proxyApiRequest).toHaveBeenCalledTimes(1);
      const calledUrl = proxyApiRequest.mock.calls[0][0];
      expect(calledUrl).toBe(site.buildUrl(encodedParams));
      // 인코딩이 빠지면(리뷰어의 3곳 제거 재현) 원문 값이 그대로 URL에 남아 위 단정이 깨진다.
      for (const raw of Object.values(params)) {
        if (/[^\w.-]/.test(raw)) expect(calledUrl).not.toContain(raw);
      }
    });
  });
});
