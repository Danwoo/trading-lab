/**
 * #355 DB 그물 — **관리자 화면에서 만든 계정이 로그인 직후 제품 화면에 들어갈 수 있는가.**
 *
 * 왜 mock 이 아니라 DB 인가: 이 결함의 피해는 「권한 행이 없다」에서 끝나지 않고 **그 계정의
 * 로그인 판정(`resolveAccountContext`)이 `authorId: null` 을 내어 메뉴가 통째로 비는 것**까지다.
 * 그 연쇄는 실제 라우트가 실제 DB 에 남긴 행을 실제 판정 함수가 읽어야 보인다 — prisma 를 mock 하면
 * 「라우트가 create 를 불렀다」까지만 보고, 지키려는 성질(만든 계정이 제품에 들어간다)은 검사되지 않는다.
 *
 * 경로는 둘이고 둘 다 실제 핸들러를 부른다:
 * - 생성(POST `/api/common/system/adminuser`) — 이슈가 지목한 자리. Better Auth 의 `signUpEmail` 만
 *   대역으로 세우고(실제 사용자 행은 대역이 prisma 로 만든다) 나머지는 전부 진짜다.
 * - 수정(PUT `/api/common/system/adminuser/[email]`) — 「대기」로 만든 계정을 승인하는 자리. 공용
 *   워크스페이스면 게스트, 자기 개인 워크스페이스면 운영자를 붙여야 한다(규칙 `lib/auth/defaultAuthor.ts`).
 *
 * 실행 전제·방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단과 같다 (`npm run test:db`).
 *
 * **fail-closed**: 시나리오 표가 비면 실패한다. 검사한 시나리오 수를 출력에 남긴다.
 */
import { afterAll, describe, expect, it, vi } from "vitest";
import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID } from "@/constants/protected";
import { WRITE_AUTHOR_IDS } from "@/constants/writeAccess";

const SYSADMIN = { id: "sysadmin-355", email: "sysadmin-355@dbtest.example.com" };

// withAuth 가 부르는 세션만 대역으로 세운다 — 검증 대상(라우트·defaultAuthor·prisma)은 진짜를 쓴다.
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: {
          user: SYSADMIN,
          // SYS_ADMIN_AUTHOR_ID — 워크스페이스를 고르는 생성은 시스템관리자의 자리다.
          session: { authorId: "admin", workspaceId: null },
        },
        headers: new Headers(),
      })),
      // Better Auth 가 하는 일 중 이 그물이 필요로 하는 것만: `tn_user` 행을 만들고 id 를 돌려준다.
      signUpEmail: vi.fn(async ({ body }: { body: { email: string; name: string } }) => {
        const id = randomUUID();
        await prisma.user.create({ data: { id, email: body.email, name: body.name, emailVerified: true } });
        return { user: { id, email: body.email } };
      }),
    },
  },
}));

// 인가 게이트는 세션 스냅샷이 아니라 **지금의 DB** 로 권한을 판정한다 (#354). 요청자(시스템관리자)는
// DB 에 없는 대역이라 그 판정만 대역으로 맞추고, **만들어진 계정의 판정은 진짜 함수**를 쓴다 —
// 그것이 이 그물이 보려는 축이다.
vi.mock("@/lib/auth/accountContext", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/auth/accountContext")>();
  return {
    ...real,
    resolveAccountContext: vi.fn(async (userId: string) =>
      userId === SYSADMIN.id
        ? { block: null, authorId: "admin", workspaceId: null }
        : real.resolveAccountContext(userId),
    ),
  };
});

// 에디션은 SaaS 로 고정한다 — OEM 이면 생성 라우트가 「유일 활성 공용 워크스페이스」를 찾아
// 이 DB 의 상태에 따라 갈린다. 두 에디션 모두 권한 부여는 같은 코드를 탄다.
vi.mock("@/utils/common/edition", () => ({ isOEM: () => false, isSaaS: () => true }));

const { POST } = await import("@/app/api/common/system/adminuser/route");
const { PUT } = await import("@/app/api/common/system/adminuser/[email]/route");
const { resolveAccountContext } = await import("@/lib/auth/accountContext");

const created: { emails: string[]; workspaceIds: number[] } = { emails: [], workspaceIds: [] };

async function ensureAuthors() {
  for (const authorId of [GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID]) {
    await prisma.author.upsert({
      where: { author_id: authorId },
      create: { author_id: authorId, author_nm: authorId },
      update: {},
    });
  }
}

async function makeWorkspace(isPersonal: boolean) {
  const tag = randomUUID().slice(0, 20);
  const workspace = await prisma.workspace.create({
    data: {
      workspace_code: `ws-355-${tag}`,
      workspace_nm: isPersonal ? "355 개인 워크스페이스" : "355 공용 워크스페이스",
      use_at: "Y",
      is_personal: isPersonal,
    },
  });
  created.workspaceIds.push(workspace.id);
  return workspace.id;
}

function postRequest(body: Record<string, unknown>): NextRequest {
  return new NextRequest("http://localhost/api/common/system/adminuser", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function putRequest(
  email: string,
  body: Record<string, unknown>,
): [NextRequest, { params: Promise<{ email: string }> }] {
  const request = new NextRequest(`http://localhost/api/common/system/adminuser/${encodeURIComponent(email)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return [request, { params: Promise.resolve({ email }) }];
}

const rolesOf = async (email: string) =>
  (await prisma.authorMember.findMany({ where: { user_id: email }, select: { author_id: true } })).map(
    (m) => m.author_id,
  );

const userOf = async (email: string) => {
  const user = await prisma.user.findUnique({ where: { email }, select: { id: true } });
  expect(user, `${email} 사용자 행이 없다 — 생성이 실패했다`).not.toBeNull();
  return user!;
};

async function createViaAdmin(workspaceId: number, apprAt: "Y" | "N") {
  const email = `${randomUUID()}@dbtest.example.com`;
  created.emails.push(email);
  const res = await POST(
    postRequest({
      email,
      name: "355-probe",
      dept: "조사",
      workspace_id: workspaceId,
      use_at: "Y",
      appr_at: apprAt,
      password: "probepass1234",
    }),
    { params: Promise.resolve({}) },
  );
  expect(res.status, `관리자 생성이 200 이 아니다: ${await res.clone().text()}`).toBe(200);
  return email;
}

afterAll(async () => {
  const users = await prisma.user.findMany({ where: { email: { in: created.emails } }, select: { id: true } });
  const userIds = users.map((u) => u.id);
  await prisma.authorMember.deleteMany({ where: { user_id: { in: created.emails } } });
  await prisma.workspaceMember.deleteMany({ where: { user_id: { in: userIds } } });
  await prisma.baSession.deleteMany({ where: { userId: { in: userIds } } });
  await prisma.user.deleteMany({ where: { id: { in: userIds } } });
  await prisma.workspace.deleteMany({ where: { id: { in: created.workspaceIds } } });
});

describe("#355 관리자가 만든 계정의 기본 권한 — 실제 라우트 + 실제 DB", () => {
  let scenarios = 0;

  it("공용 워크스페이스에 「승인」으로 만들면 게스트가 붙고, 로그인 판정이 그 권한을 낸다", async () => {
    await ensureAuthors();
    const sharedId = await makeWorkspace(false);
    const email = await createViaAdmin(sharedId, "Y");

    expect(await rolesOf(email), "만든 직후 권한이 0건이다 — #355 의 원래 증상").toEqual([GUEST_AUTHOR_ID]);
    expect(GUEST_AUTHOR_ID, "남의 공용 워크스페이스에 넣은 계정이 쓰기 역할을 받았다").not.toBeOneOf([
      ...WRITE_AUTHOR_IDS,
    ]);

    // 로그인·인가가 쓰는 그 판정 함수가 이 계정을 「권한 있는 계정」으로 본다 — 메뉴가 열리는 전제다.
    const { id } = await userOf(email);
    expect(await resolveAccountContext(id)).toEqual({ block: null, authorId: GUEST_AUTHOR_ID, workspaceId: sharedId });
    scenarios++;
  });

  it("「대기」로 만들면 아직 권한이 없고, 승인(PUT)하는 순간 게스트가 붙는다", async () => {
    await ensureAuthors();
    const sharedId = await makeWorkspace(false);
    const email = await createViaAdmin(sharedId, "N");
    expect(await rolesOf(email), "승인 전에 권한이 붙었다").toEqual([]);

    const [req, ctx] = putRequest(email, {
      name: "355-probe",
      dept: "조사",
      workspace_id: sharedId,
      use_at: "Y",
      appr_at: "Y",
    });
    const res = await PUT(req, ctx);
    expect(res.status, `승인 PUT 이 200 이 아니다: ${await res.clone().text()}`).toBe(200);
    expect(await rolesOf(email)).toEqual([GUEST_AUTHOR_ID]);
    scenarios++;
  });

  it("자기 개인 워크스페이스의 계정을 승인하면 주인(운영자)이 붙는다 — 수정 경로도 같은 규칙", async () => {
    await ensureAuthors();
    const personalId = await makeWorkspace(true);
    const id = randomUUID();
    const email = `${id}@dbtest.example.com`;
    created.emails.push(email);
    await prisma.user.create({
      data: { id, email, name: "355-owner", emailVerified: true, workspace_id: personalId, use_at: "Y", appr_at: "N" },
    });
    await prisma.workspaceMember.create({
      data: { workspace_id: personalId, user_id: id, role: "owner", is_default: true },
    });

    const [req, ctx] = putRequest(email, { name: "355-owner", workspace_id: personalId, use_at: "Y", appr_at: "Y" });
    const res = await PUT(req, ctx);
    expect(res.status, `승인 PUT 이 200 이 아니다: ${await res.clone().text()}`).toBe(200);
    expect(await rolesOf(email), "개인 워크스페이스의 주인에게 게스트를 줬다 — 저장·실행이 전부 403 이 된다").toEqual([
      SIGNUP_AUTHOR_ID,
    ]);
    scenarios++;
  });

  it("이미 권한이 있는 계정의 승인을 내렸다 올려도 권한이 중복으로 붙지 않는다", async () => {
    await ensureAuthors();
    const sharedId = await makeWorkspace(false);
    const email = await createViaAdmin(sharedId, "Y");
    const body = { name: "355-probe", dept: "조사", workspace_id: sharedId, use_at: "Y" };

    // 승인을 내렸다 다시 올리면 부여 블록에 두 번째로 들어간다 — 「이미 있나」를 안 세면 PK 위반으로 500 이다.
    expect((await PUT(...putRequest(email, { ...body, appr_at: "N" }))).status).toBe(200);
    const res = await PUT(...putRequest(email, { ...body, appr_at: "Y" }));
    expect(res.status, `재승인 PUT 이 200 이 아니다: ${await res.clone().text()}`).toBe(200);
    expect(await rolesOf(email)).toEqual([GUEST_AUTHOR_ID]);
    scenarios++;
  });

  it("시나리오를 하나 이상 검사했다 (fail-closed)", () => {
    expect(scenarios).toBeGreaterThan(0);
    console.info(`[#355] 관리자 생성·승인 시나리오 ${scenarios}건을 실제 DB 로 검사했다`);
  });
});
