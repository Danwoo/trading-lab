// #400 — 부분 갱신처럼 보이는 PUT 이 **생략한 필드를 조용히 null 로 덮어쓰던** 것을 막는 그물.
//
// 결함의 모양: 한 `update()` 안에서 어떤 필드는 생략=무시(Prisma `undefined`), 어떤 필드는
// 생략=삭제(`?? null`·`|| null`)로 갈렸다. 가장 비싼 자리가 `adminuser` 의 `workspace_id` 다 —
// 배정 해제로 끝나지 않고 **일반관리자 권한 삭제 + 세션 전면 무효화**까지 연쇄한다.
//
// 리드 결정(이 PR): **PUT = 전체 표현**. 본문을 클라이언트와 같은 스키마로 경계에서 파싱하고,
// 필수 필드가 빠진 본문은 400 으로 거절한다. 그래서 "이름만 고치려던 PUT" 은 이제 `use_at`·
// `appr_at` 누락으로 400 이고, `workspace_id` 연쇄까지 도달하지 못한다. 근거는
// `app/api/common/system/adminuser/[email]/route.ts` 의 PUT 주석.
//
// **검증 경계** — prisma 는 mock 이다. 보는 것은 **핸들러가 DB 로 내보내는 update data** 이고,
// 실제 행이 어떻게 바뀌는지는 여기서 보지 않는다(그 축은 dbtest 의 몫).
//
// 337·389 와 같은 이유로 `npm run test:api-regressions` 로만 돈다 (생성된 Prisma 클라이언트 필요).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

// ── mock ──────────────────────────────────────────────────────────────────

vi.mock("@/env", () => ({
  env: { NODE_ENV: "development", BACKEND_SERVICE_URL: "http://backend.test" },
}));

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        // SYS_ADMIN_AUTHOR_ID("admin") — 이 그물이 보는 것은 권한이 아니라 본문 계약이다.
        response: { user: { id: "u1", email: "admin@example.com" }, session: { authorId: "admin", workspaceId: 1 } },
        headers: new Headers(),
      })),
    },
  },
}));

vi.mock("@/lib/auth/authUtils", () => ({
  assertSameWorkspaceOrSysAdmin: vi.fn(async () => null),
  assertTargetNotSysAdmin: vi.fn(async () => null),
  assertAssignableWorkspace: vi.fn(async () => null),
  checkLastActiveSysAdmin: vi.fn(async () => null),
  invalidateUserSessions: vi.fn(async () => undefined),
  syncDefaultWorkspaceMembership: vi.fn(async () => undefined),
  deleteUserCascade: vi.fn(async () => undefined),
  hashPassword: vi.fn(async () => "hashed"),
  normalizeEmail: (e: string) => e,
  workspaceScopedUserWhere: (workspaceId: number) => ({ workspace_id: workspaceId }),
}));

type PrismaCall = { model: string; method: string; args: any };
const prismaCalls: PrismaCall[] = [];

/** 389 그물과 같은 형태의 만능 스텁 — 호출 인자를 그대로 기록한다. */
const prismaStub: any = new Proxy(
  {},
  {
    get(_target, model: string) {
      if (model === "then") return undefined;
      return new Proxy(
        {},
        {
          get(_t, method: string) {
            return (args: any) => {
              prismaCalls.push({ model, method: String(method), args });
              if (method === "count") return Promise.resolve(0);
              if (method === "findMany") return Promise.resolve([]);
              // 존재 확인·update 응답 — 라우트가 뒤에서 읽는 필드를 채워 둔다.
              return Promise.resolve({ id: "u1", email: "target@example.com", workspace_id: 3, appr_at: "Y" });
            };
          },
        },
      );
    },
  },
);

vi.mock("@/lib/prisma/client", () => ({ prisma: prismaStub }));

// ── 헬퍼 ──────────────────────────────────────────────────────────────────

function makeRequest(method: string, body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/test", {
    method,
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

const updateCalls = () => prismaCalls.filter((c) => c.method === "update" || c.method === "updateMany");

beforeEach(() => {
  prismaCalls.length = 0;
});

// ── adminuser PUT ─────────────────────────────────────────────────────────

describe("#400 adminuser PUT — 전체 표현이 아니면 쓰기까지 가지 않는다", () => {
  const call = async (body: unknown) => {
    const mod: any = await import("@/app/api/common/system/adminuser/[email]/route");
    return (await mod.PUT(makeRequest("PUT", body), {
      params: Promise.resolve({ email: "target@example.com" }),
    })) as Response;
  };

  // 결함이 있을 때: 200 + update({ workspace_id: null }) — 배정 해제 → 권한 강등 → 강제 로그아웃.
  it.each([
    ["이름만 보낸 부분 갱신", { name: "새 이름" }],
    ["부서만 보낸 부분 갱신", { dept: "새 부서" }],
    ["use_at 만 빠진 본문", { name: "n", appr_at: "Y" }],
    ["appr_at 만 빠진 본문", { name: "n", use_at: "Y" }],
    ["빈 본문", {}],
  ])("%s 은 400 이고 user.update 를 부르지 않는다", async (_label, body) => {
    const res = await call(body);
    expect(res.status).toBe(400);
    expect(updateCalls()).toEqual([]);
  });

  it("JSON 이 아닌 본문은 500 이 아니라 400 이다", async () => {
    const res = await call("{not json");
    expect(res.status).toBe(400);
    expect(updateCalls()).toEqual([]);
  });

  it("workspace_id 에 Prisma 필터 객체를 넣으면 경계에서 거절한다 (#400 코멘트)", async () => {
    // 예전엔 이 값이 검증 없이 assertAssignableWorkspace → where.id 로 들어가, 존재 확인이
    // "요청한 그 워크스페이스"가 아니라 "조건에 맞는 아무 워크스페이스"를 찾았다.
    const res = await call({ name: "n", use_at: "Y", appr_at: "Y", workspace_id: { gt: 0 } });
    expect(res.status).toBe(400);
    expect(updateCalls()).toEqual([]);
  });

  it("전체 표현은 그대로 통과하고 생략한 선택 필드는 명시적 null 로 나간다", async () => {
    const res = await call({ name: "n", use_at: "Y", appr_at: "Y" });
    expect(res.status).not.toBe(400);
    const update = updateCalls().find((c) => c.model === "user");
    expect(update, "user.update 가 불리지 않았다").toBeTruthy();
    expect(update!.args.data).toMatchObject({ name: "n", dept: null, workspace_id: null, use_at: "Y", appr_at: "Y" });
  });

  it("본문에 없는 키는 update 로 새지 않는다 (스키마가 걸러낸다)", async () => {
    const res = await call({ name: "n", use_at: "Y", appr_at: "Y", reg_id: "attacker@example.com" });
    expect(res.status).not.toBe(400);
    const update = updateCalls().find((c) => c.model === "user");
    expect(Object.keys(update!.args.data)).not.toContain("reg_id");
  });

  // ── 값이 손상된 경우 ────────────────────────────────────────────────────
  //
  // 「필수 필드 누락」만 보던 위 그물이 못 보던 축이다. `workspace_id` 는 설계상
  // `Optional(int())`(null 이 정상 상태)라 `use_at`·`appr_at` 처럼 필수화해서 막을 수 없다 —
  // 전체표현 계약의 방어선이 이 필드엔 처음부터 걸리지 않았다.
  //
  // 결함이 있을 때: `Optional()` 이 변환 실패를 `undefined` 로 접고, `data.workspace_id ?? null`
  // 이 그걸 명시적 null 로 흡수해 **200 + 배정 해제 + 일반관리자 권한 삭제 + 세션 무효화**.
  // `"3e2"` 는 더 나쁘다 — 해제가 아니라 존재하지도 않을 300번으로 조용히 배정된다.
  //
  // 이 표는 「숫자로 읽히지만 사람이 안 쓴 표기」 축이다. 잘못된 JSON 타입 축(`{gt:0}`)은
  // 바로 위 전용 케이스가 본다.
  const CORRUPTED_WORKSPACE_IDS: [string, unknown][] = [
    ["숫자로 안 읽히는 문자열", "garbage"],
    ["지수 표기(→300)", "3e2"],
    ["16진수 표기(→16)", "0x10"],
    ["2진수 표기(→5)", "0b101"],
    ["8진수 표기(→15)", "0o17"],
    ["구분자 표기", "1_000"],
    ["빈 배열", []],
  ];

  it.each(CORRUPTED_WORKSPACE_IDS)(
    "workspace_id 가 %s 이면 400 이고 user.update 를 부르지 않는다",
    async (_label, workspace_id) => {
      const res = await call({ name: "n", use_at: "Y", appr_at: "Y", workspace_id });
      expect(res.status).toBe(400);
      expect(updateCalls()).toEqual([]);
    },
  );

  it("손상값 표가 줄지 않았다 (fail-closed)", () => {
    expect(CORRUPTED_WORKSPACE_IDS.length).toBe(7);
  });

  // 거절이 정상 경로를 갉아먹지 않는지 — 화면이 실제로 보내는 payload 형태다.
  // SelectBox(valueExpr="id")는 항목의 id(숫자)를, clear 버튼은 null 을 낸다.
  it.each([
    ["숫자 (SelectBox 선택)", 7, 7],
    ["십진수 문자열", "7", 7],
    ["null (clear 버튼)", null, null],
    ["키 자체가 없음", undefined, null],
  ])("workspace_id 가 %s 이면 통과하고 %s 로 나간다", async (_label, workspace_id, expected) => {
    const body: Record<string, unknown> = { name: "n", use_at: "Y", appr_at: "Y" };
    if (workspace_id !== undefined) body.workspace_id = workspace_id;

    const res = await call(body);
    expect(res.status).not.toBe(400);
    const update = updateCalls().find((c) => c.model === "user");
    expect(update, "user.update 가 불리지 않았다").toBeTruthy();
    expect(update!.args.data.workspace_id).toBe(expected);
  });
});

// ── menu PUT ──────────────────────────────────────────────────────────────

describe("#400 menu PUT — 전체 표현이 아니면 쓰기까지 가지 않는다", () => {
  const call = async (body: unknown) => {
    const mod: any = await import("@/app/api/common/system/menu/[menu_id]/route");
    return (await mod.PUT(makeRequest("PUT", body), { params: Promise.resolve({ menu_id: "m-test" }) })) as Response;
  };

  it.each([
    ["url 만 보낸 부분 갱신", { url: "/new" }],
    ["menu_nm 이 빠진 본문", { menu_level: 1, sort_ordr: 1, use_at: "Y" }],
    ["빈 본문", {}],
  ])("%s 은 400 이고 menu.update 를 부르지 않는다", async (_label, body) => {
    const res = await call(body);
    expect(res.status).toBe(400);
    expect(updateCalls()).toEqual([]);
  });

  it("전체 표현은 그대로 통과하고 생략한 선택 필드는 명시적 null 로 나간다", async () => {
    const res = await call({ menu_nm: "메뉴", menu_level: 1, sort_ordr: 1, use_at: "Y" });
    expect(res.status).not.toBe(400);
    const update = updateCalls().find((c) => c.model === "menu");
    expect(update!.args.data).toMatchObject({
      menu_nm: "메뉴",
      upper_menu_id: null,
      url: null,
      icon: null,
      use_at: "Y",
    });
  });
});

// ── mypage PATCH ──────────────────────────────────────────────────────────

describe("#400 mypage PATCH — dept 생략은 '건드리지 않음'이 아니라 거절이다", () => {
  const call = async (body: unknown) => {
    const mod: any = await import("@/app/api/common/mypage/route");
    return (await mod.PATCH(makeRequest("PATCH", body), {})) as Response;
  };

  it("dept 가 빠진 본문은 부서를 조용히 지우지 않고 거절한다", async () => {
    const res = await call({ email: "admin@example.com", name: "이름" });
    const body = await res.json();
    expect(body.result).toBe(false);
    expect(body.name).toBe("dept");
    expect(updateCalls()).toEqual([]);
  });

  it("문자열이 아닌 password 는 500 이 아니라 검증 실패다 (#388 과 같은 축)", async () => {
    const res = await call({ email: "admin@example.com", name: "이름", dept: "부서", password: 12345678 });
    const body = await res.json();
    expect(body.result).toBe(false);
    expect(body.name).toBe("password");
    expect(updateCalls()).toEqual([]);
  });

  it("전체 표현은 그대로 통과한다 — 빈 dept 는 null 로 저장된다", async () => {
    const res = await call({ email: "admin@example.com", name: "이름", dept: "" });
    const body = await res.json();
    expect(body.result).toBe(true);
    const update = updateCalls().find((c) => c.model === "user");
    expect(update!.args.data).toMatchObject({ name: "이름", dept: null });
  });
});
