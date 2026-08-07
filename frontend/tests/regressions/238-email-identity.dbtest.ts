/**
 * #238 회귀 그물 — **이메일로 사람을 식별하는 자리가 정규화를 거치는가.**
 *
 * `tn_author_member.user_id` 는 email 자연키다. 참조 무결성은 FK(`→ tn_user.email`,
 * `ON UPDATE CASCADE`)가 이미 지키고 그 계약은 `verify_frontend_fk_referential_actions.py` 가
 * 잠근다. 남는 위험은 **같은 사람을 다른 문자열로 부르는 것**이다 — 이 두 라우트만
 * `normalizeEmail` 경계를 안 거쳤다(다른 이메일 라우트는 withAuth 의 `scopeEmailParam` 이나
 * 라우트 자신이 통과시킨다).
 *
 * 정규화가 빠지면 두 가지가 난다:
 *   (1) 권한 부여가 FK 위반 500 으로 죽는다 (대문자 주소가 `tn_user.email` 과 안 맞는다)
 *   (2) `invalidateUserSessions` 가 사용자를 못 찾고 **조용히 아무것도 안 한다** — 권한은
 *       바뀌었는데 그 사람의 세션에 박힌 옛 `authorId` 가 만료까지 살아남는다.
 * (2)는 예외도 로그도 없어서, 세션 축을 직접 세지 않으면 그물이 못 잡는다.
 *
 * 실행 전제·방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단과 같다 (`npm run test:db`).
 */
import { afterAll, describe, expect, it, vi } from "vitest";
import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";

vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: {
          user: { id: "sysadmin-238", email: "sysadmin@dbtest.example.com" },
          session: { authorId: "admin", workspaceId: null },
        },
        headers: new Headers(),
      })),
    },
  },
}));

const { POST: authorUserPost } = await import("@/app/api/common/system/author/[author_id]/user/route");
const { DELETE: authorUserDelete } = await import("@/app/api/common/system/author/[author_id]/user/[user_id]/route");

type Fixture = { userId: string; storedEmail: string; mixedCaseEmail: string; authorId: string; sessionId: string };

async function createFixture(): Promise<Fixture> {
  const userId = randomUUID();
  // 저장된 주소는 정규화된 소문자 — 가입·관리자 생성 경로가 normalizeEmail 을 거치므로 이것이 실제 형태다.
  const storedEmail = `${userId}@dbtest.example.com`.toLowerCase();
  // 클라이언트가 보낼 수 있는 형태: 사람이 손으로 친 대문자 + 앞뒤 공백.
  const mixedCaseEmail = `  ${userId.toUpperCase()}@DBTEST.Example.COM  `;
  const authorId = `at-238-${userId.slice(0, 10)}`;
  const sessionId = randomUUID();

  await prisma.user.create({
    data: { id: userId, email: storedEmail, name: "238-user", appr_at: "Y", use_at: "Y" },
  });
  await prisma.author.create({ data: { author_id: authorId, author_nm: "238 테스트 권한" } });
  await prisma.baSession.create({
    data: {
      id: sessionId,
      expiresAt: new Date(Date.now() + 3600_000),
      token: randomUUID(),
      createdAt: new Date(),
      updatedAt: new Date(),
      userId,
      authorId: "user",
    },
  });

  return { userId, storedEmail, mixedCaseEmail, authorId, sessionId };
}

async function cleanupFixture(f: Fixture): Promise<void> {
  await prisma.authorMember.deleteMany({ where: { author_id: f.authorId } });
  await prisma.author.deleteMany({ where: { author_id: f.authorId } });
  await prisma.baSession.deleteMany({ where: { userId: f.userId } });
  await prisma.user.deleteMany({ where: { id: f.userId } });
}

describe("#238 — 권한 부여·제거가 이메일을 정규화해 같은 사람을 가리킨다", () => {
  it("대문자·공백 섞인 주소로 권한을 줘도 저장된 주소로 매핑되고 세션이 무효화된다", async () => {
    const f = await createFixture();
    try {
      const request = new NextRequest(`http://localhost/api/common/system/author/${f.authorId}/user`, {
        method: "POST",
        body: JSON.stringify({ user_id: f.mixedCaseEmail }),
        headers: { "content-type": "application/json" },
      });
      const response = await authorUserPost(request, { params: Promise.resolve({ author_id: f.authorId }) });

      expect(response.status).toBe(200);
      const members = await prisma.authorMember.findMany({ where: { author_id: f.authorId } });
      expect(members).toHaveLength(1);
      expect(members[0].user_id).toBe(f.storedEmail);

      // 조용한 실패 축 — 권한이 바뀌었으면 그 사람의 세션은 끊겨야 한다.
      expect(await prisma.baSession.findMany({ where: { userId: f.userId } })).toHaveLength(0);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("대문자·공백 섞인 주소로 권한을 거둬도 저장된 주소의 매핑이 지워지고 세션이 무효화된다", async () => {
    const f = await createFixture();
    try {
      await prisma.authorMember.create({ data: { author_id: f.authorId, user_id: f.storedEmail } });

      const request = new NextRequest(`http://localhost/api/common/system/author/${f.authorId}/user/x`, {
        method: "DELETE",
      });
      const response = await authorUserDelete(request, {
        params: Promise.resolve({ author_id: f.authorId, user_id: f.mixedCaseEmail }),
      });

      expect(response.status).toBe(200);
      expect(await prisma.authorMember.findMany({ where: { author_id: f.authorId } })).toHaveLength(0);
      expect(await prisma.baSession.findMany({ where: { userId: f.userId } })).toHaveLength(0);
    } finally {
      await cleanupFixture(f);
    }
  });
});

afterAll(async () => {
  await prisma.$disconnect();
});
