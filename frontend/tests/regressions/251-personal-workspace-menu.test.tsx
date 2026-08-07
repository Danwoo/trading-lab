// @vitest-environment jsdom
//
// #251 회귀 그물 — **개인 워크스페이스로 가입한 사용자의 사이드바가 실제로 차는가.**
//
// 결함(수정 전): `ensurePersonalWorkspace` 가 워크스페이스와 owner 멤버십만 만들고
// `tn_workspace_menu` 는 한 행도 안 만들었다. 네비게이션은 일반 사용자에게
// **권한 메뉴 ∩ 워크스페이스 메뉴** 만 노출하므로(`menu/navigation` 의 `isVisible`)
// 교집합이 공집합이 되어 메뉴 API 가 `{"items":[]}` 를 반환했고 사이드바가 빈 채로 떴다.
//
// 이 파일은 **기본 데이터 → 가입 → 메뉴 API → 사이드바 렌더**를 한 줄로 잇는다:
//   ① `prisma/init/seed.sql` 을 파싱해 메뉴·권한메뉴 기본값을 그대로 읽고(하드코딩하지 않는다 —
//      시드가 바뀌면 이 그물이 함께 움직여야 한다)
//   ② 진짜 `ensurePersonalWorkspace` 를 인메모리 prisma 위에서 돌려 워크스페이스 메뉴를 만들고
//   ③ 진짜 `GET /api/common/system/menu/navigation` 핸들러를 그 상태에서 호출하고
//   ④ 그 응답을 `navStore` 에 넣어 진짜 `Sidebar` 를 렌더해 **메뉴가 보이는지** 확인한다.
//
// **검증 경계**: prisma 는 인메모리 스텁이다 — 실제 DB 의 제약(FK·유니크)이나 트랜잭션 롤백은
// 여기서 보지 않는다. 보는 것은 "두 축(권한·워크스페이스)이 교차해 화면에 메뉴가 남는가"다.
//
// 337·389·400 과 같은 이유로 `npm run test:api-regressions` 로만 돈다 (생성된 Prisma 클라이언트 필요).
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const PERSONAL_WORKSPACE_ID = 42;
const SIGNUP_USER_ID = "user-1";
const SIGNUP_EMAIL = "someone@gmail.com";

// ── seed.sql 파싱 (기본 데이터의 단일 출처) ────────────────────────────────────

const repoFrontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const seedSql = readFileSync(path.join(repoFrontendDir, "prisma/init/seed.sql"), "utf8");

/** `INSERT INTO <table> ... VALUES` 부터 다음 `;` 까지의 값 블록. 못 찾으면 실패(fail-closed). */
function valuesBlock(table: string): string {
  const match = new RegExp(`INSERT INTO ${table}\\b[\\s\\S]*?VALUES([\\s\\S]*?);`, "i").exec(seedSql);
  expect(match, `seed.sql 에서 ${table} INSERT 블록을 찾지 못했다`).not.toBeNull();
  return (match as RegExpExecArray)[1];
}

interface SeedMenu {
  menu_id: string;
  menu_nm: string;
  upper_menu_id: string | null;
  menu_level: number;
  sort_ordr: number;
  use_at: string;
  url: string | null;
  icon: string | null;
}

const seedMenus: SeedMenu[] = Array.from(
  valuesBlock("tn_menu").matchAll(
    /\('([^']+)', *'([^']*)', *(NULL|'[^']*'), *(\d+), *(\d+), *'([YN])', *(NULL|'[^']*'), *(NULL|'[^']*')/g,
  ),
).map((m) => {
  const unquote = (v: string) => (v === "NULL" ? null : v.slice(1, -1));
  return {
    menu_id: m[1],
    menu_nm: m[2],
    upper_menu_id: unquote(m[3]),
    menu_level: Number(m[4]),
    sort_ordr: Number(m[5]),
    use_at: m[6],
    url: unquote(m[7]),
    icon: unquote(m[8]),
  };
});

const seedAuthorMenus: { author_id: string; menu_id: string }[] = Array.from(
  valuesBlock("tn_author_menu").matchAll(/\('([^']+)', *'([^']+)'/g),
).map((m) => ({ author_id: m[1], menu_id: m[2] }));

// 파싱이 조용히 0건이 되면 아래 단언이 전부 무의미해진다 — 그 자체를 먼저 막는다.
expect(seedMenus.length, "seed.sql 에서 파싱한 메뉴가 0건이다 — 파서가 시드 형식과 어긋났다").toBeGreaterThan(5);
expect(seedAuthorMenus.length, "seed.sql 에서 파싱한 권한별 메뉴가 0건이다").toBeGreaterThan(5);

// ── 인메모리 prisma ────────────────────────────────────────────────────────────

const workspaceMenuRows: { workspace_id: number; menu_id: string }[] = [];

const prismaStub: any = {
  user: {
    findUniqueOrThrow: async () => ({ name: "가입자" }),
  },
  workspace: {
    upsert: async () => ({ id: PERSONAL_WORKSPACE_ID }),
  },
  workspaceMember: {
    upsert: async () => ({}),
  },
  menu: {
    findMany: async ({ where }: any = {}) =>
      seedMenus
        .filter((m) => (where?.use_at ? m.use_at === where.use_at : true))
        .filter((m) => (where?.menu_id?.in ? where.menu_id.in.includes(m.menu_id) : true))
        .sort((a, b) => a.menu_level - b.menu_level || a.sort_ordr - b.sort_ordr),
  },
  workspaceMenu: {
    createMany: async ({ data, skipDuplicates }: any) => {
      for (const row of data) {
        const exists = workspaceMenuRows.some((r) => r.workspace_id === row.workspace_id && r.menu_id === row.menu_id);
        if (exists && skipDuplicates) continue;
        workspaceMenuRows.push({ workspace_id: row.workspace_id, menu_id: row.menu_id });
      }
      return { count: data.length };
    },
    findMany: async ({ where }: any = {}) =>
      workspaceMenuRows.filter((r) => (where?.workspace_id ? r.workspace_id === where.workspace_id : true)),
  },
  authorMember: {
    findMany: async () => [{ author_id: "user" }],
  },
  authorMenu: {
    findMany: async ({ where }: any = {}) =>
      seedAuthorMenus.filter((r) => (where?.author_id?.in ? where.author_id.in.includes(r.author_id) : true)),
  },
  $transaction: async (fn: any) => fn(prismaStub),
};

vi.mock("@/lib/prisma/client", () => ({ prisma: prismaStub }));
vi.mock("@/env", () => ({ env: { NODE_ENV: "test", BACKEND_SERVICE_URL: "http://backend.test" } }));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: {
          user: { id: SIGNUP_USER_ID, email: SIGNUP_EMAIL },
          // 가입 직후 SaaS 사용자 — 기본 권한 `user`, 홈은 자기 개인 워크스페이스.
          session: { authorId: "user", workspaceId: PERSONAL_WORKSPACE_ID },
        },
        headers: new Headers(),
      })),
    },
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/",
}));

const { ensurePersonalWorkspace } = await import("@/lib/auth/authUtils");
const { PERSONAL_WORKSPACE_DEFAULT_MENU_IDS, DEFAULT_USER_AUTHOR_ID } = await import("@/constants/protected");
const { GET } = await import("@/app/api/common/system/menu/navigation/route");
const { Sidebar } = await import("@/components/shared/Layout/Sidebar");
const { useNavStore } = await import("@/stores/shared/navStore");

interface NavItem {
  id: string;
  text: string;
  path?: string;
  items?: NavItem[];
}

/** 가입 흐름이 하는 일(개인 워크스페이스 생성) → 메뉴 API 호출. 실제 구현을 그대로 탄다. */
async function signupThenFetchNav(): Promise<NavItem[]> {
  await ensurePersonalWorkspace(SIGNUP_USER_ID, SIGNUP_EMAIL);
  const response = await GET(new Request("http://localhost/api/common/system/menu/navigation") as any, undefined);
  const body = await response.json();
  return body.data?.items ?? body.items ?? [];
}

beforeEach(() => {
  workspaceMenuRows.length = 0;
  useNavStore.setState({ items: [] });
  cleanup();
});

describe("개인 워크스페이스 사이드바 (#251)", () => {
  it("가입이 만든 개인 워크스페이스에 기본 업무 메뉴가 부여된다", async () => {
    await ensurePersonalWorkspace(SIGNUP_USER_ID, SIGNUP_EMAIL);
    expect(workspaceMenuRows.map((r) => r.menu_id).sort()).toEqual([...PERSONAL_WORKSPACE_DEFAULT_MENU_IDS].sort());
    expect(workspaceMenuRows.every((r) => r.workspace_id === PERSONAL_WORKSPACE_ID)).toBe(true);
  });

  it("여러 번 불려도 같은 행이 겹쳐 쌓이지 않는다", async () => {
    await ensurePersonalWorkspace(SIGNUP_USER_ID, SIGNUP_EMAIL);
    await ensurePersonalWorkspace(SIGNUP_USER_ID, SIGNUP_EMAIL);
    expect(workspaceMenuRows).toHaveLength(PERSONAL_WORKSPACE_DEFAULT_MENU_IDS.length);
  });

  it("메뉴 API 가 빈 목록이 아니라 업무 메뉴를 돌려준다", async () => {
    const items = await signupThenFetchNav();

    // 결함 시절엔 여기가 [] 였다.
    expect(items.length).toBeGreaterThan(0);
    const leafIds = items.flatMap((parent) => (parent.items ?? []).map((child) => child.id));
    for (const menuId of PERSONAL_WORKSPACE_DEFAULT_MENU_IDS) {
      expect(leafIds, `${menuId} 가 네비게이션에 없다`).toContain(menuId);
    }
  });

  it("사이드바가 실제로 찬다 — 터미널·관심종목이 보이고 경로가 붙어 있다", async () => {
    const user = userEvent.setup();
    const items = await signupThenFetchNav();
    useNavStore.setState({ items });

    render(
      <Sidebar isDrawerOpen>
        <div>본문</div>
      </Sidebar>,
    );

    // 대분류(업무관리)가 보이고, 펼치면 잎 메뉴가 보인다.
    const group = screen.getByRole("treeitem", { name: /업무관리/ });
    expect(group).toBeTruthy();
    await user.click(group);

    expect(screen.getByRole("treeitem", { name: /터미널/ })).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /관심종목/ })).toBeTruthy();

    // 잎 메뉴에 이동 경로가 실제로 붙어 있어야 클릭이 화면을 연다.
    const terminal = items.flatMap((p) => p.items ?? []).find((c) => c.id === "mbiz1008");
    expect(terminal?.path).toBe("/terminal");
  });

  it("권한 축과 워크스페이스 축이 어긋나지 않는다 — seed.sql 의 기본 권한이 기본 메뉴를 전부 갖는다", () => {
    const defaultAuthorMenus = seedAuthorMenus
      .filter((r) => r.author_id === DEFAULT_USER_AUTHOR_ID)
      .map((r) => r.menu_id);
    expect(defaultAuthorMenus.length, `seed.sql 에 ${DEFAULT_USER_AUTHOR_ID} 권한의 메뉴가 0건이다`).toBeGreaterThan(0);
    for (const menuId of PERSONAL_WORKSPACE_DEFAULT_MENU_IDS) {
      expect(
        defaultAuthorMenus,
        `기본 권한(${DEFAULT_USER_AUTHOR_ID})에 ${menuId} 가 없어 사이드바에서 사라진다`,
      ).toContain(menuId);
    }
  });
});
