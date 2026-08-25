/**
 * #354 DB 그물 — **권한·계정 상태의 정본이 「지금의 DB」인가.**
 *
 * `resolveAccountContext` 는 로그인 훅(`auth.ts` 의 `session.create.before`)과 인가
 * 게이트(`withAuth`)가 함께 부르는 단일 술어다. 이 파일은 그 술어를 실제 Postgres 로 돌려
 * "권한을 회수하면 그 다음 판정부터 회수된 것으로 나오는가"를 검사한다 — mock 으로는
 * 술어 자신이 검사되지 않고 대역의 재현만 남는다.
 *
 * 실행 전제·방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단과 같다 (`npm run test:db`).
 *
 * **fail-closed**: 아래 시나리오 표가 비면 실패한다. 검사한 시나리오 수를 출력에 남긴다.
 */
import { afterAll, describe, expect, it } from "vitest";
import { randomUUID } from "node:crypto";
import { prisma } from "@/lib/prisma/client";
import { resolveAccountContext } from "@/lib/auth/accountContext";
import { GENERAL_ADMIN_AUTHOR_ID, GUEST_AUTHOR_ID, SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

const created: { userIds: string[]; workspaceIds: number[]; emails: string[] } = {
  userIds: [],
  workspaceIds: [],
  emails: [],
};

async function makeUser(opts: { authors?: string[]; use_at?: string; appr_at?: string; workspaceActive?: boolean }) {
  const id = randomUUID();
  const email = `${id}@dbtest.example.com`;
  for (const authorId of opts.authors ?? []) {
    await prisma.author.upsert({
      where: { author_id: authorId },
      create: { author_id: authorId, author_nm: authorId },
      update: {},
    });
  }
  const workspace = await prisma.workspace.create({
    data: {
      workspace_code: `ws-354-${id.slice(0, 22)}`,
      workspace_nm: "354 워크스페이스",
      use_at: opts.workspaceActive === false ? "N" : "Y",
      is_personal: false,
    },
  });
  await prisma.user.create({
    data: {
      id,
      email,
      name: "354-probe",
      emailVerified: true,
      workspace_id: workspace.id,
      use_at: opts.use_at ?? "Y",
      appr_at: opts.appr_at ?? "Y",
    },
  });
  await prisma.workspaceMember.create({
    data: { workspace_id: workspace.id, user_id: id, role: "member", is_default: true },
  });
  for (const authorId of opts.authors ?? []) {
    await prisma.authorMember.create({ data: { author_id: authorId, user_id: email } });
  }
  created.userIds.push(id);
  created.workspaceIds.push(workspace.id);
  created.emails.push(email);
  return { id, email, workspaceId: workspace.id };
}

afterAll(async () => {
  await prisma.authorMember.deleteMany({ where: { user_id: { in: created.emails } } });
  await prisma.workspaceMember.deleteMany({ where: { user_id: { in: created.userIds } } });
  await prisma.user.deleteMany({ where: { id: { in: created.userIds } } });
  await prisma.workspace.deleteMany({ where: { id: { in: created.workspaceIds } } });
});

describe("resolveAccountContext — DB 가 정본이다 (#354)", () => {
  let scenarios = 0;

  it("권한을 회수하면 그 즉시 대표 권한이 사라진다", async () => {
    const user = await makeUser({ authors: [GENERAL_ADMIN_AUTHOR_ID] });
    const before = await resolveAccountContext(user.id);
    expect(before).toEqual({ block: null, authorId: GENERAL_ADMIN_AUTHOR_ID, workspaceId: user.workspaceId });

    await prisma.authorMember.deleteMany({ where: { user_id: user.email, author_id: GENERAL_ADMIN_AUTHOR_ID } });

    const after = await resolveAccountContext(user.id);
    expect(after).toEqual({ block: null, authorId: null, workspaceId: user.workspaceId });
    scenarios++;
  });

  it("여러 권한을 가지면 우선순위대로 대표 권한을 고른다", async () => {
    const user = await makeUser({ authors: [GUEST_AUTHOR_ID, SYS_ADMIN_AUTHOR_ID] });
    expect((await resolveAccountContext(user.id)).authorId).toBe(SYS_ADMIN_AUTHOR_ID);
    scenarios++;
  });

  it("계정을 비활성으로 바꾸면 차단된다", async () => {
    const user = await makeUser({ authors: [GUEST_AUTHOR_ID] });
    expect((await resolveAccountContext(user.id)).block).toBeNull();

    await prisma.user.update({ where: { id: user.id }, data: { use_at: "N" } });
    expect((await resolveAccountContext(user.id)).block).toBe("InactiveUser");
    scenarios++;
  });

  it("승인이 철회되면 차단된다", async () => {
    const user = await makeUser({ authors: [GUEST_AUTHOR_ID] });
    await prisma.user.update({ where: { id: user.id }, data: { appr_at: "N" } });
    expect((await resolveAccountContext(user.id)).block).toBe("PendingApproval");

    await prisma.user.update({ where: { id: user.id }, data: { appr_at: "R" } });
    expect((await resolveAccountContext(user.id)).block).toBe("RejectedUser");
    scenarios++;
  });

  it("워크스페이스를 비활성으로 바꾸면 일반 사용자는 차단되고 시스템관리자는 통과한다", async () => {
    const user = await makeUser({ authors: [GUEST_AUTHOR_ID] });
    await prisma.workspace.update({ where: { id: user.workspaceId }, data: { use_at: "N" } });
    expect((await resolveAccountContext(user.id)).block).toBe("InactiveWorkspace");

    await prisma.authorMember.create({ data: { author_id: SYS_ADMIN_AUTHOR_ID, user_id: user.email } });
    await prisma.author.upsert({
      where: { author_id: SYS_ADMIN_AUTHOR_ID },
      create: { author_id: SYS_ADMIN_AUTHOR_ID, author_nm: SYS_ADMIN_AUTHOR_ID },
      update: {},
    });
    expect((await resolveAccountContext(user.id)).block).toBeNull();
    scenarios++;
  });

  it("사용자 행이 사라지면 차단된다", async () => {
    expect((await resolveAccountContext(randomUUID())).block).toBe("PendingApproval");
    scenarios++;
  });

  it("검사한 시나리오가 0건이 아니다", () => {
    console.info(`[#354 dbtest] 검사한 시나리오: ${scenarios}건`);
    expect(scenarios).toBeGreaterThan(0);
  });
});
