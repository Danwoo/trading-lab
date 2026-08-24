// #389 — 형식이 깨진 필터가 "필터 없음"으로 삼켜져 **제약 없는 쿼리가 DB 까지 도달**하던 것을
// 막는 그물. 파서 단위 테스트(tests/lib/grid/filters.test.ts)와 층이 다르다:
//
//   파서 단위     — convertFilterToPrismaWhere 가 던지는가
//   이 파일(종단) — **실제 라우트 핸들러**가 400 을 내고 prisma 에 아예 안 가는가
//
// 이 층이 따로 필요한 이유는 #306 이 이미 보여줬다: 파이썬 쪽에서 parse_filter 는 "(1 = 0)" 을
// 냈는데 소비자(build_filter_params)가 그 호출 자체를 건너뛰어, 파서만 고친 상태로 실제 HTTP
// 경로는 여전히 전건을 반환했다. 파서가 옳아도 소비자가 삼키면 사용자에게는 결함 그대로다.
//
// **공격 형태**: 그리드 UI 로는 만들 수 없는 filter 쿼리스트링을 직접 던진다(권한은 정상).
// 결함이 있을 때: 200 + prisma.<model>.findMany({ where: {} }) — 필터를 걸었는데 제약이 0이다.
// 고친 뒤: 400 + findMany 미호출.
//
// **검증 경계** — prisma 클라이언트는 mock 이라 "행이 몇 건 나오는가"는 여기서 보지 않는다.
// 보는 것은 **핸들러가 DB 로 내보내는 where** 다: 그것이 비어 있으면(제약 0) 어떤 DB 를 붙여도
// 전건이다. "전건이 실제로 나온다"는 축은 DevExtreme 평가기가 심판을 서는
// scripts/verify_filter_negation.mjs(malformed_never_returns_all_rows)와 backend-service 의
// build_filter_params 종단 테스트가 각자 자기 층에서 덮는다.
//
// 무거운 의존성(better-auth·env·prisma 접속)은 mock 한다 — 337-path-traversal.test.ts 와 같은
// 패턴이고, 같은 이유로 `npm run test:api-regressions` 로만 돈다(생성된 Prisma 클라이언트 필요).
//
// **이 파일이 세 이슈를 함께 진다** (#389 · #399 · #401). 셋 다 "같은 라우트 집합이 클라이언트가
// 보낸 filter/sort 를 어떻게 다루는가"를 종단에서 보는 그물이고, 위 ROUTES 표와 mock 하네스를
// 공유한다 — 파일을 나누면 하네스가 세 벌이 되고 라우트 표도 세 벌이 되어 한쪽만 늘어난다
// (`vi.mock` 은 테스트 파일 안에서만 끌어올려지므로 하네스를 헬퍼로 뽑을 수 없다).
//   #389 — 형식이 깨진 필터가 "필터 없음"으로 삼켜져 전건이 나가던 것
//   #399 — URL 경로·테넌트가 정한 스코프 술어를 클라 filter 가 얕은 스프레드로 덮던 것
//   #401 — sort selector 무검증 · 필터 재귀 깊이 상한 부재로 클라 입력 하나가 500 이 되던 것

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const COMMON_API_ROOT = path.join(FRONTEND_ROOT, "app/api/common");

/** `convertFilterToPrismaWhere` 를 실제로 부르는 route.ts 를 파일시스템에서 매번 다시 찾는다. */
function listFilterRouteFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFilterRouteFiles(full));
    else if (entry.isFile() && entry.name === "route.ts") {
      if (fs.readFileSync(full, "utf-8").includes("convertFilterToPrismaWhere(")) out.push(full);
    }
  }
  return out;
}

const DISCOVERED = listFilterRouteFiles(COMMON_API_ROOT).map((f) => path.relative(FRONTEND_ROOT, f));

// ── mock ──────────────────────────────────────────────────────────────────
// vi.mock 은 최상단 리터럴로 — vitest 가 아래 동적 import 보다 먼저 끌어올린다.

vi.mock("@/env", () => ({
  env: { NODE_ENV: "development", BACKEND_SERVICE_URL: "http://backend.test" },
}));

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        // SYS_ADMIN_AUTHOR_ID("admin") — requireSysAdmin 라우트도 통과시켜, 필터 검증에
        // 닿기 전에 403 으로 끊기지 않게 한다. 이 그물이 보는 것은 권한이 아니라 필터다.
        response: { user: { id: "u1", email: "admin@example.com" }, session: { authorId: "admin", workspaceId: 1 } },
        headers: new Headers(),
      })),
    },
  },
}));

// 인가 게이트는 세션 스냅샷이 아니라 **지금의 DB** 로 권한을 판정한다 (#354). 이 그물이
// 보는 축은 그게 아니므로, 위 대역 세션과 같은 값을 내는 얇은 대역을 세워 게이트를 통과시킨다.
// 게이트 자체는 `tests/regressions/354-stale-authorization.test.ts` 가 검사한다.
vi.mock("@/lib/auth/accountContext", () => ({
  resolveAccountContext: vi.fn(async () => ({ block: null, authorId: "admin", workspaceId: 1 })),
}));

vi.mock("@/lib/auth/authUtils", () => ({
  assertSameWorkspaceOrSysAdmin: vi.fn(async () => null),
  assertTargetNotSysAdmin: vi.fn(async () => null),
  normalizeEmail: (e: string) => e,
  workspaceScopedUserWhere: (workspaceId: number) => ({ workspace_id: workspaceId }),
}));

type PrismaCall = { model: string; method: string; args: any };
const prismaCalls: PrismaCall[] = [];

/**
 * 어떤 모델 이름이 와도 응답하는 prisma 스텁 — 라우트마다 다른 모델을 쓰므로 표를 손으로
 * 유지하지 않는다(새 라우트가 늘어도 따라간다). 호출 인자를 그대로 기록해 where 를 검사한다.
 */
const prismaStub: any = new Proxy(
  {},
  {
    get(_target, model: string) {
      if (model === "then") return undefined; // await 대상이 아니다
      return new Proxy(
        {},
        {
          get(_t, method: string) {
            return (args: any) => {
              prismaCalls.push({ model, method: String(method), args });
              if (method === "count") return Promise.resolve(0);
              if (method === "findMany") return Promise.resolve([]);
              return Promise.resolve({}); // findUnique 등 — 존재 확인 분기를 통과시킨다
            };
          },
        },
      );
    },
  },
);

vi.mock("@/lib/prisma/client", () => ({ prisma: prismaStub }));

// ── 검사 표 ───────────────────────────────────────────────────────────────

type FilterRoute = {
  /** import 경로 */
  module: string;
  /** 파일시스템 스캔 결과와 대조할 상대 경로 */
  file: string;
  /** 동적 세그먼트 params */
  params?: Record<string, string>;
  /** 이 라우트가 실제로 거는 정상 필터의 필드 — 대조(control)용 */
  controlField: string;
  /**
   * 이 라우트가 URL·세션에서 **서버가 정하는** 술어 (#399). 클라 filter 가 같은 키를 보내도
   * 이 값의 제약은 살아남아야 한다. 동적 세그먼트가 있는 라우트는 반드시 채운다(아래 대조).
   */
  scope?: { key: string; value: unknown; attacker: unknown };
};

const ROUTES: FilterRoute[] = [
  {
    module: "@/app/api/common/system/adminuser/route",
    file: "app/api/common/system/adminuser/route.ts",
    controlField: "email",
  },
  {
    module: "@/app/api/common/system/author/route",
    file: "app/api/common/system/author/route.ts",
    controlField: "author_nm",
  },
  {
    module: "@/app/api/common/system/code-group/route",
    file: "app/api/common/system/code-group/route.ts",
    controlField: "group_code",
  },
  {
    module: "@/app/api/common/system/code-group/[group_code]/code/route",
    file: "app/api/common/system/code-group/[group_code]/code/route.ts",
    params: { group_code: "G1" },
    controlField: "code",
    scope: { key: "group_code", value: "G1", attacker: "OTHER_GROUP" },
  },
  {
    module: "@/app/api/common/system/menu/route",
    file: "app/api/common/system/menu/route.ts",
    controlField: "menu_nm",
  },
  {
    module: "@/app/api/common/system/workspace/route",
    file: "app/api/common/system/workspace/route.ts",
    controlField: "workspace_nm",
  },
  {
    module: "@/app/api/common/system/workspace/[workspace_id]/domain/route",
    file: "app/api/common/system/workspace/[workspace_id]/domain/route.ts",
    params: { workspace_id: "1" },
    controlField: "domain",
    scope: { key: "workspace_id", value: 1, attacker: 99 },
  },
  {
    module: "@/app/api/common/system/workspace/[workspace_id]/user/route",
    file: "app/api/common/system/workspace/[workspace_id]/user/route.ts",
    params: { workspace_id: "1" },
    controlField: "email",
    // 위 mock 의 workspaceScopedUserWhere 가 `{ workspace_id: <id> }` 를 돌려준다.
    scope: { key: "workspace_id", value: 1, attacker: 99 },
  },
];

// 그리드 UI 로는 만들 수 없지만 쿼리스트링으로는 얼마든지 던질 수 있는 형태 — 결함이 있을 때
// 전부 `{}`(제약 없음)로 읽혔다. 목록은 공유 fixture 의 ref "#389" 축과 같다.
const MALFORMED_FILTERS = [
  '["and"]',
  '["a","="]',
  '[1,"=",1]',
  '["a","=",1,"and",2]',
  '["!","x"]',
  '["a","=",1,"and"]',
  '["and",["a","=",1]]',
  "{not json",
  '{"a":1}',
];

function makeRequest(query: string): NextRequest {
  return new NextRequest(`http://localhost/api/test?${query}`, { method: "GET" });
}

async function callGet(route: FilterRoute, query: string) {
  const mod: any = await import(route.module);
  const props = route.params ? { params: Promise.resolve(route.params) } : {};
  return (await mod.GET(makeRequest(query), props)) as Response;
}

beforeEach(() => {
  prismaCalls.length = 0;
});

describe("#389 정적 대조 — 필터를 쓰는 라우트를 하나도 빠뜨리지 않았다", () => {
  it("검사 대상이 0건이 아니다 (fail-closed)", () => {
    expect(DISCOVERED.length).toBeGreaterThan(0);
  });

  it("표가 파일시스템 스캔 결과와 일치한다 (라우트가 늘면 표도 늘어야 한다)", () => {
    expect([...ROUTES.map((r) => r.file)].sort()).toEqual([...DISCOVERED].sort());
  });
});

describe(`#389 종단 net — 필터 라우트 ${ROUTES.length}곳 × 형식 오류 ${MALFORMED_FILTERS.length}종`, () => {
  describe.each(ROUTES)("$file", (route) => {
    it.each(MALFORMED_FILTERS)("filter=%s 는 400 이고 prisma 까지 가지 않는다", async (malformed) => {
      const res = await callGet(route, `filter=${encodeURIComponent(malformed)}&take=10&skip=0`);

      expect(res.status).toBe(400);
      // 결함이 있을 때 여기서 findMany 가 `where: {}` 로 불렸다 — 제약 0 = 전건.
      const listCalls = prismaCalls.filter((c) => c.method === "findMany" || c.method === "count");
      expect(listCalls).toEqual([]);
    });

    it("정상 필터는 그대로 통과하고 제약이 where 에 실려 나간다 (거절이 정상 경로를 갉아먹지 않는다)", async () => {
      const valid = JSON.stringify([route.controlField, "contains", "x"]);
      const res = await callGet(route, `filter=${encodeURIComponent(valid)}&take=10&skip=0`);

      expect(res.status).not.toBe(400);
      const findMany = prismaCalls.find((c) => c.method === "findMany" && c.args?.where);
      expect(findMany, "findMany 가 where 와 함께 불리지 않았다").toBeTruthy();
      // where 안 어딘가에 이 필드 제약이 실려 있어야 한다 — 라우트마다 스코프 술어와 합치는
      // 방식(얕은 스프레드 / AND 배열)이 달라 문자열 포함으로 본다.
      expect(JSON.stringify(findMany!.args.where)).toContain(route.controlField);
    });
  });
});

describe("#389 목록이 줄지 않았다 (fail-closed)", () => {
  it("형식 오류 케이스 수가 기대치와 같다", () => {
    expect(MALFORMED_FILTERS.length).toBe(9);
  });
});

// ── #399 스코프 술어를 클라 filter 가 덮지 못한다 ─────────────────────────

/**
 * `where` 트리에서 **반드시 성립하는**(AND 경로로만 도달하는) `key` 제약의 값들을 모은다.
 * `OR`·`NOT` 아래는 "반드시"가 아니므로 세지 않는다 — 스코프가 논리합의 한 항으로 밀려나면
 * 그건 이미 경계가 아니다.
 */
function pinnedValues(where: any, key: string): unknown[] {
  const out: unknown[] = [];
  const walk = (node: any) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) return node.forEach(walk);
    for (const [k, v] of Object.entries(node)) {
      if (k === "OR" || k === "NOT") continue;
      if (k === "AND") walk(v);
      else if (k === key) out.push(v && typeof v === "object" && "equals" in (v as any) ? (v as any).equals : v);
    }
  };
  walk(where);
  return out;
}

describe("#399 정적 대조 — 클라 filter 를 where 에 얕은 스프레드로 합치는 자리가 없다", () => {
  // 얕은 스프레드는 **같은 키면 뒤가 이긴다**. `{ ...baseWhere, ...clientFilter }` 한 줄이
  // URL 이 선언한 스코프를 클라가 통째로 갈아치우는 문이 된다 — 인스턴스가 아니라 형태를 막는다.
  // 대상은 `convertFilterToPrismaWhere` 를 부르는 라우트뿐이다(= 클라가 통제하는 객체를 합치는
  // 자리). 서버가 스스로 만든 술어를 조건부 스프레드로 얹는 것(adminuser/options/route.ts)은
  // 이 클래스가 아니라서 대상 밖이다.
  const SHALLOW_MERGE_RE = /\bwhere\b[^=\n]*=\s*\{\s*\.\.\./;

  it("검사 대상이 0건이 아니다 (fail-closed)", () => {
    expect(DISCOVERED.length).toBeGreaterThan(0);
  });

  it(`필터 라우트 ${DISCOVERED.length}곳 어디에도 얕은 스프레드 합성이 없다`, () => {
    const offenders = DISCOVERED.filter((rel) =>
      SHALLOW_MERGE_RE.test(fs.readFileSync(path.join(FRONTEND_ROOT, rel), "utf-8")),
    );
    expect(`검사 ${DISCOVERED.length}건 / 위반 ${offenders.length}건: ${offenders.join(", ")}`).toBe(
      `검사 ${DISCOVERED.length}건 / 위반 0건: `,
    );
  });

  it("동적 세그먼트가 있는 라우트는 스코프 술어를 이 표에 선언한다 (그물이 조용히 비지 않게)", () => {
    const missing = ROUTES.filter((r) => r.params && !r.scope).map((r) => r.file);
    expect(missing).toEqual([]);
    expect(ROUTES.filter((r) => r.scope).length).toBeGreaterThan(0);
  });
});

const SCOPED_ROUTES = ROUTES.filter((r) => r.scope);

describe(`#399 종단 net — 스코프 있는 라우트 ${SCOPED_ROUTES.length}곳`, () => {
  it.each(SCOPED_ROUTES)("$file — 같은 키를 덮어쓰려는 filter 가 와도 스코프 제약이 살아남는다", async (route) => {
    const scope = route.scope!;
    const attack = JSON.stringify([scope.key, "=", scope.attacker]);
    const res = await callGet(route, `filter=${encodeURIComponent(attack)}&take=10&skip=0`);

    expect(res.status).not.toBe(400);
    const findMany = prismaCalls.find((c) => c.method === "findMany" && c.args?.where);
    expect(findMany, "findMany 가 where 와 함께 불리지 않았다").toBeTruthy();
    // 결함이 있을 때 이 값은 [attacker] 였다 — URL 이 가리키는 것이 where 에서 사라졌다.
    expect(pinnedValues(findMany!.args.where, scope.key)).toContain(scope.value);
  });
});

// ── #401 sort selector 미검증 · 재귀 깊이 상한 부재 ───────────────────────

/** 깊이 33 — 두 파서가 공유하는 상한(32)을 한 단 넘긴다. 상한 근거는 filters.ts 주석. */
function nestedFilter(depth: number): unknown {
  let node: unknown = ["a", "=", 1];
  for (let i = 1; i < depth; i++) node = ["!", node];
  return node;
}

const MALFORMED_SORTS = [
  // 식별자 미검증 — 예전엔 그대로 Prisma orderBy 키가 됐다(파이썬 parse_sort 는 400 이었다).
  '[{"selector":"a; DROP TABLE t"}]',
  '[{"selector":"1bad"}]',
  // 객체가 아닌 항 — `sortItem.selector` 에서 TypeError 가 나 400 이 아니라 500 으로 샜다.
  "[null]",
  '["name"]',
  // 배열 항 — JS 에서 `typeof []` 는 `"object"` 라 위 검사를 통과했다. `selector` 가 undefined
  // 라 조용히 건너뛰어져 **기본 정렬로 폴백(200)** 했고, 파이썬 `parse_sort` 는
  // `isinstance(s, dict)` 로 같은 입력을 400 으로 거절했다 — #295·#401 이 없앤 판정 발산이
  // 이 좁은 모양에서만 남아 있었다.
  '[["a"]]',
  "[[]]",
  '[[{"selector":"a"}]]',
];

describe(`#401 종단 net — 필터 라우트 ${ROUTES.length}곳 × sort 형식 오류 ${MALFORMED_SORTS.length}종`, () => {
  describe.each(ROUTES)("$file", (route) => {
    it.each(MALFORMED_SORTS)("sort=%s 는 400 이고 prisma 까지 가지 않는다", async (malformed) => {
      const res = await callGet(route, `sort=${encodeURIComponent(malformed)}&take=10&skip=0`);

      expect(res.status).toBe(400);
      const listCalls = prismaCalls.filter((c) => c.method === "findMany" || c.method === "count");
      expect(listCalls).toEqual([]);
    });

    it("정상 sort 는 그대로 통과한다 (거절이 정상 경로를 갉아먹지 않는다)", async () => {
      const valid = JSON.stringify([{ selector: route.controlField, desc: true }]);
      const res = await callGet(route, `sort=${encodeURIComponent(valid)}&take=10&skip=0`);

      expect(res.status).not.toBe(400);
      const findMany = prismaCalls.find((c) => c.method === "findMany" && c.args?.orderBy);
      expect(JSON.stringify(findMany?.args.orderBy)).toContain(route.controlField);
    });

    it("상한을 넘긴 중첩 필터는 500 이 아니라 400 이다", async () => {
      const deep = JSON.stringify(nestedFilter(33));
      const res = await callGet(route, `filter=${encodeURIComponent(deep)}&take=10&skip=0`);

      // 결함이 있을 때: RangeError(Maximum call stack size exceeded) → 진짜 Error 라 5번 fallback 500.
      expect(res.status).toBe(400);
      const listCalls = prismaCalls.filter((c) => c.method === "findMany" || c.method === "count");
      expect(listCalls).toEqual([]);
    });

    it("상한과 같은 깊이의 중첩 필터는 통과한다 (상한이 정상 경로를 갉아먹지 않는다)", async () => {
      const atLimit = JSON.stringify(nestedFilter(32));
      const res = await callGet(route, `filter=${encodeURIComponent(atLimit)}&take=10&skip=0`);

      expect(res.status).not.toBe(400);
    });
  });

  it("sort 형식 오류 케이스 수가 기대치와 같다 (fail-closed)", () => {
    expect(MALFORMED_SORTS.length).toBe(7);
  });
});
