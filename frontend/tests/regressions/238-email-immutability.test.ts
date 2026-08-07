// #238 — **이메일은 사용자 신원 키다. 오늘 그것을 바꾸는 경로가 없다는 것을 잠근다.**
//
// 배경: `public` 스키마(alembic 소유)의 이메일 컬럼 셋은 `frontend` 스키마(Prisma 소유)의
// `tn_user.email` 을 FK 없이 참조한다 — 스키마 교차 FK 가 없기 때문이다.
//
//   · `public.tn_research_document.user_id`   FK 없음 → 이메일이 바뀌면 조용히 끊긴다
//   · `public.workspace_doc_chunk.user_id`    FK 없음 → 조용히 끊긴다 (doc-search 자가 DDL)
//   · `public.tn_scheduler_member.email`      식별 키는 account_id 라 식별은 안전, 표시용만 낡는다
//
// 앞의 둘은 사용자의 리서치 문서와 RAG 청크다 — 끊기면 본인 자료에 접근하지 못하는데, DB 가
// 막아주지 않으므로 아무도 모른 채 진행된다. 2026-08-02 리드 결정은 「이메일 변경 기능이 없어
// 오늘은 안 터진다」였고, 이 파일이 그 **전제를 실행 가능한 불변식으로** 바꾼다.
//
// 이메일 변경을 켜는 사람은 여기서 빨간불을 보게 되고, 그때 위 세 컬럼을 함께 처리해야 한다
// (처방 후보는 #238 본문 — `tn_user.id` 대리키 전환 / 스키마 교차 FK / 애플리케이션 계층 이관).
//
// **검증 경계** — prisma 는 스텁이다. 보는 것은 **핸들러가 DB 로 내보내는 update data 와
// where** 이고, 실제 행이 어떻게 바뀌는지는 보지 않는다(그 축은 dbtest 의 몫). Better Auth 의
// `changeEmail` 플러그인처럼 라우트 핸들러를 거치지 않는 경로는 (3)의 정적 스캔이 덮는다.
//
// 337·389·400 과 같은 이유로 `npm run test:api-regressions` 로만 돈다 (생성된 Prisma 클라이언트 필요).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

const SESSION_EMAIL = "owner@example.com";

// ── mock ──────────────────────────────────────────────────────────────────

vi.mock("@/env", () => ({
  env: { NODE_ENV: "development", BACKEND_SERVICE_URL: "http://backend.test" },
}));

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: { user: { id: "u1", email: SESSION_EMAIL }, session: { authorId: "admin", workspaceId: 1 } },
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

/** 400 그물과 같은 형태의 만능 스텁 — 호출 인자를 그대로 기록한다. */
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
              return Promise.resolve({ id: "u1", email: SESSION_EMAIL, workspace_id: 1, appr_at: "Y" });
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

const userWrites = () =>
  prismaCalls.filter((c) => c.model === "user" && (c.method === "update" || c.method === "updateMany"));

beforeEach(() => {
  prismaCalls.length = 0;
});

// ── (1) 마이페이지 — 남의 주소로 바꾸려는 시도는 쓰기까지 가지 않는다 ────────

describe("#238 (1) 마이페이지 PATCH — 이메일은 수정 대상이 아니다", () => {
  const call = async (body: unknown) => {
    const mod: any = await import("@/app/api/common/mypage/route");
    return (await mod.PATCH(makeRequest("PATCH", body), { params: Promise.resolve({}) })) as Response;
  };

  it("세션과 다른 이메일을 실으면 403 이고 user 쓰기가 없다", async () => {
    const res = await call({ email: "someone.else@example.com", name: "새 이름", dept: "" });
    expect(res.status).toBe(403);
    expect(userWrites()).toEqual([]);
  });

  it("정상 본문이어도 update data 에 email 이 없고 where 는 세션 이메일이다", async () => {
    const res = await call({ email: SESSION_EMAIL, name: "새 이름", dept: "" });
    expect(res.status).not.toBe(403);
    const write = userWrites().find((c) => c.method === "update");
    expect(write, "user.update 가 불리지 않았다").toBeTruthy();
    expect(Object.keys(write!.args.data)).not.toContain("email");
    expect(write!.args.where).toEqual({ email: SESSION_EMAIL });
  });
});

// ── (2) 관리자 사용자 수정 — 본문의 email 은 갱신 대상이 아니다 ─────────────

describe("#238 (2) adminuser PUT — 본문에 email 을 실어도 갱신되지 않는다", () => {
  const call = async (body: unknown) => {
    const mod: any = await import("@/app/api/common/system/adminuser/[email]/route");
    return (await mod.PUT(makeRequest("PUT", body), {
      params: Promise.resolve({ email: "target@example.com" }),
    })) as Response;
  };

  it("전체 표현 + email 침입 시도 → update data 에 email 이 없다", async () => {
    const res = await call({ name: "n", use_at: "Y", appr_at: "Y", email: "hijack@example.com" });
    expect(res.status).not.toBe(500);
    const write = userWrites().find((c) => c.method === "update");
    expect(write, "user.update 가 불리지 않았다").toBeTruthy();
    expect(Object.keys(write!.args.data)).not.toContain("email");
    // 대상 식별은 경로 파라미터로만 — 본문이 대상을 바꾸지 못한다.
    expect(write!.args.where).toEqual({ email: "target@example.com" });
  });
});

// ── (3) 드리프트 — 사용자 행을 쓰는 자리가 늘면 알린다 ──────────────────────

describe("#238 (3) 사용자 행을 쓰는 자리 전수", () => {
  // 새 라우트가 tn_user 를 쓰기 시작하면 이 목록과 어긋나 빨간불이 된다 — 그때 그 라우트가
  // email 을 건드리는지 확인하고, 건드린다면 #238 의 public 스키마 컬럼 3개를 함께 처리해야 한다.
  const EXPECTED_USER_WRITE_SITES = [
    "app/api/common/mypage/route.ts",
    "app/api/common/system/adminuser/[email]/route.ts",
  ].sort();

  const SCAN_ROOTS = ["app/api", "components", "lib"];
  const WRITE_PATTERN = /prisma\.user\.(update|updateMany|upsert)\b/;

  function listSourceFiles(dir: string): string[] {
    const out: string[] = [];
    if (!fs.existsSync(dir)) return out;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) out.push(...listSourceFiles(full));
      else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
    }
    return out;
  }

  it("tn_user 를 쓰는 파일 목록이 알려진 것과 같다", () => {
    const files = SCAN_ROOTS.flatMap((root) => listSourceFiles(path.join(FRONTEND_ROOT, root)));
    // 검사 대상이 0건이면 통과가 아니다 — 스캔 루트가 사라져도 조용히 초록이 되지 않게 (#252 계열).
    expect(files.length, "스캔 대상 파일이 0건이다 — SCAN_ROOTS 를 확인하라").toBeGreaterThan(0);

    const found = files
      .filter((f) => WRITE_PATTERN.test(fs.readFileSync(f, "utf8")))
      .map((f) => path.relative(FRONTEND_ROOT, f))
      .sort();
    expect(found).toEqual(EXPECTED_USER_WRITE_SITES);
  });

  it("Better Auth 설정에 changeEmail 이 켜져 있지 않다", () => {
    // 라우트 핸들러를 거치지 않는 경로 — 켜지면 (1)(2)의 그물을 우회한다.
    const authSource = fs.readFileSync(path.join(FRONTEND_ROOT, "lib/auth/auth.ts"), "utf8");
    expect(authSource).not.toMatch(/changeEmail/);
  });
});
