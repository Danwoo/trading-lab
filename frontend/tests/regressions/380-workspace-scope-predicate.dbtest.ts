/**
 * #380 동적 그물 — 「멤버십으로만 소속된 사용자」가 소속 판정을 하는 **모든** 경로에서 보이는가.
 *
 * 소속을 적는 자리가 둘이라(스칼라 `tn_user.workspace_id` · 다대다 `tn_workspace_member`) 술어도
 * 둘로 갈릴 수 있다. 갈리면 fail-closed 방향이라 데이터가 새지는 않지만, 같은 사용자가 목록에는
 * 보이는데 단건은 "사용자를 찾을 수 없습니다"가 되고 권한도 못 주는 상태가 된다 — 운영자가
 * 그 계정을 다룰 수 없다.
 *
 * 짝인 `380-workspace-scope-predicate.test.ts` 는 소스 텍스트에서 옛 형태를 막는다. 이 파일은
 * 실제 DB 로 **행동**을 본다: 두 축(스칼라만 / 멤버십만)에 각각 놓인 사용자를 심고, 다섯 경로가
 * 둘 다 잡는지 확인한다. 술어를 스칼라 단독으로 되돌리면 멤버십만 있는 사용자 쪽이 전부 빨강이 된다.
 *
 * 실행 전제·방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단과 같다 (`npm run test:db`).
 */
import { afterAll, describe, expect, it, vi } from "vitest";
import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import {
  assertSameWorkspaceOrSysAdmin,
  workspaceScopedEmailWhere,
  workspaceScopedUserWhere,
} from "@/lib/auth/authUtils";

/** withAuth 가 읽는 세션 — 케이스마다 갈아끼운다(시스템관리자 / 그 워크스페이스 운영자). */
let currentSession: { user: { id: string; email: string }; session: { authorId: string; workspaceId: number | null } };

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({ response: currentSession, headers: new Headers() })),
    },
  },
}));

// 인가 게이트는 세션 스냅샷이 아니라 **지금의 DB** 로 권한을 판정한다 (#354). 세션 자체가
// 위처럼 대역이므로 그 판정도 같은 값을 내는 대역으로 맞춘다 — 어긋나면 게이트가 401 로 끊어
// 이 그물이 보려는 축에 닿지 못한다. 게이트 자신은 `354-stale-authorization.test.ts` 가 본다.
vi.mock("@/lib/auth/accountContext", () => ({
  resolveAccountContext: vi.fn(async () => ({
    block: null,
    authorId: currentSession.session.authorId,
    workspaceId: currentSession.session.workspaceId,
  })),
}));

const { GET: workspaceUserGet } = await import("@/app/api/common/system/workspace/[workspace_id]/user/route");
const { GET: adminUserOptionsGet } = await import("@/app/api/common/system/adminuser/options/route");

type Fixture = {
  workspaceId: number;
  workspaceCode: string;
  otherWorkspaceId: number;
  otherWorkspaceCode: string;
  scalarOnlyId: string;
  scalarOnlyEmail: string;
  membershipOnlyId: string;
  membershipOnlyEmail: string;
  outsiderId: string;
  outsiderEmail: string;
};

async function createFixture(): Promise<Fixture> {
  const scalarOnlyId = randomUUID();
  const membershipOnlyId = randomUUID();
  const outsiderId = randomUUID();
  const workspaceCode = `ws-380a-${scalarOnlyId.slice(0, 22)}`;
  const otherWorkspaceCode = `ws-380b-${outsiderId.slice(0, 22)}`;

  const workspace = await prisma.workspace.create({
    data: { workspace_code: workspaceCode, workspace_nm: "380 대상 워크스페이스", is_personal: false },
  });
  const other = await prisma.workspace.create({
    data: { workspace_code: otherWorkspaceCode, workspace_nm: "380 남의 워크스페이스", is_personal: false },
  });

  const mk = async (id: string, name: string, workspace_id: number | null) => {
    await prisma.user.create({
      data: { id, email: `${id}@dbtest.example.com`, name, appr_at: "Y", use_at: "Y", workspace_id },
    });
  };

  // (1) 스칼라만 — 멤버십 백필 전의 기존 계정 형태.
  await mk(scalarOnlyId, "380-scalar-only", workspace.id);
  // (2) 멤버십만 — 다대다로만 소속된 계정. 스칼라 단독 술어는 이쪽을 못 본다.
  await mk(membershipOnlyId, "380-membership-only", null);
  await prisma.workspaceMember.create({
    data: { workspace_id: workspace.id, user_id: membershipOnlyId, role: "member", is_default: true },
  });
  // (3) 남의 워크스페이스 — 어느 경로에서도 보이면 안 된다(합집합이 너무 넓어지지 않았는지).
  await mk(outsiderId, "380-outsider", other.id);

  return {
    workspaceId: workspace.id,
    workspaceCode,
    otherWorkspaceId: other.id,
    otherWorkspaceCode,
    scalarOnlyId,
    scalarOnlyEmail: `${scalarOnlyId}@dbtest.example.com`,
    membershipOnlyId,
    membershipOnlyEmail: `${membershipOnlyId}@dbtest.example.com`,
    outsiderId,
    outsiderEmail: `${outsiderId}@dbtest.example.com`,
  };
}

async function cleanupFixture(f: Fixture): Promise<void> {
  const ids = [f.scalarOnlyId, f.membershipOnlyId, f.outsiderId];
  await prisma.workspaceMember.deleteMany({ where: { user_id: { in: ids } } });
  await prisma.user.deleteMany({ where: { id: { in: ids } } });
  await prisma.workspace.deleteMany({ where: { workspace_code: { in: [f.workspaceCode, f.otherWorkspaceCode] } } });
}

const sysAdminSession = () => ({
  user: { id: "sysadmin-380", email: "sysadmin@dbtest.example.com" },
  session: { authorId: "admin", workspaceId: null },
});
const operatorSession = (workspaceId: number) => ({
  user: { id: "operator-380", email: "operator@dbtest.example.com" },
  session: { authorId: "operator", workspaceId },
});

async function jsonOf(response: Response): Promise<any> {
  return await response.json();
}

describe("#380 — 멤버십으로만 소속된 사용자가 모든 경로에서 보인다", () => {
  it("술어 자신(workspaceScopedUserWhere)이 두 축을 다 잡는다", async () => {
    const f = await createFixture();
    try {
      const found = await prisma.user.findMany({
        where: workspaceScopedUserWhere(f.workspaceId),
        select: { email: true },
      });
      const emails = found.map((u) => u.email);
      expect(emails).toContain(f.scalarOnlyEmail);
      expect(emails).toContain(f.membershipOnlyEmail);
      expect(emails).not.toContain(f.outsiderEmail);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("단건 가드(assertSameWorkspaceOrSysAdmin)가 멤버십만 있는 사용자를 통과시킨다", async () => {
    const f = await createFixture();
    try {
      const session = {
        user: { ...operatorSession(f.workspaceId).user, isSysAdmin: false, workspaceId: f.workspaceId },
      };
      expect(await assertSameWorkspaceOrSysAdmin(session, f.membershipOnlyEmail)).toBeNull();
      expect(await assertSameWorkspaceOrSysAdmin(session, f.scalarOnlyEmail)).toBeNull();
      expect(await assertSameWorkspaceOrSysAdmin(session, f.outsiderEmail)).toBe("사용자를 찾을 수 없습니다.");
    } finally {
      await cleanupFixture(f);
    }
  });

  it("워크스페이스 상세의 멤버 목록에 멤버십만 있는 사용자가 뜬다", async () => {
    const f = await createFixture();
    currentSession = sysAdminSession();
    try {
      const request = new NextRequest(`http://localhost/api/common/system/workspace/${f.workspaceId}/user`);
      const response = await workspaceUserGet(request, {
        params: Promise.resolve({ workspace_id: String(f.workspaceId) }),
      });
      const body = await jsonOf(response);
      const emails = body.items.map((i: { email: string }) => i.email);
      expect(emails).toContain(f.scalarOnlyEmail);
      expect(emails).toContain(f.membershipOnlyEmail);
      expect(emails).not.toContain(f.outsiderEmail);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("사용자 피커(adminuser/options)에 멤버십만 있는 사용자가 뜬다", async () => {
    const f = await createFixture();
    currentSession = operatorSession(f.workspaceId);
    try {
      const request = new NextRequest("http://localhost/api/common/system/adminuser/options");
      const response = await adminUserOptionsGet(request, { params: Promise.resolve({}) });
      const body = await jsonOf(response);
      const emails = body.items.map((i: { email: string }) => i.email);
      expect(emails).toContain(f.scalarOnlyEmail);
      expect(emails).toContain(f.membershipOnlyEmail);
      expect(emails).not.toContain(f.outsiderEmail);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("메일 로그 스코핑(workspaceScopedEmailWhere)도 멤버십만 있는 사용자를 포함한다", async () => {
    const f = await createFixture();
    try {
      const where = (await workspaceScopedEmailWhere(f.workspaceId)) as { OR: { to: { in?: string[] } }[] };
      const inList = where.OR.flatMap((cond) => cond.to.in ?? []);
      expect(inList).toContain(f.scalarOnlyEmail);
      expect(inList).toContain(f.membershipOnlyEmail);
      expect(inList).not.toContain(f.outsiderEmail);
    } finally {
      await cleanupFixture(f);
    }
  });
});

afterAll(async () => {
  await prisma.$disconnect();
});
