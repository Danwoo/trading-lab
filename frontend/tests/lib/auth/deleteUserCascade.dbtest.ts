/**
 * `deleteUserCascade` 통합 회귀 테스트 — 실제 Postgres 를 상대로 authUtils.ts 의 TypeScript 코드를
 * **직접 호출**한다.
 *
 * 이 파일이 필요한 이유(#357 리뷰 [B]): `verify_no_orphan_personal_workspaces.py`(#280)는 감사
 * SQL 의 정밀도·재현율만 검증하고 `deleteUserCascade` 를 한 번도 실행하지 않는다 — 그 함수를
 * 통째로 되돌려도 그 스크립트는 초록으로 남는다(감사 쿼리 자신만 검사하기 때문). 그 그물은 여전히
 * 유효하지만("감사 SQL 이 정확한가") 「이번 삭제가 새는 경로가 있으면 그게 잡아야 한다」는
 * 리드 결정(#280)을 충족하려면 삭제 코드 자체를 실행하는 그물이 하나 더 있어야 한다 — 이 파일이
 * 그 그물이다.
 *
 * 별도 vitest 설정(`vitest.db.config.ts`)으로만 수집된다 — 기본 `npm test`(`vitest.config.ts`)는
 * DB 없이도 돌아야 하는 순수 유닛 테스트 스위트라 이 파일을 기본 include 에서 제외한다
 * (파일명 규약: `*.dbtest.ts`, 기본 include 글롭 `*.{test,spec}.*` 와 겹치지 않는다).
 *
 * 실행: `DATABASE_URL` 을 **두 스키마가 다 준비된** Postgres 로 잡고 `npm run test:db`
 * (cwd=frontend). CI(`frontend-ci.yml` 의 `delete-user-cascade` 잡)는 backend-service 의
 * `verify_*.py` 와 같은 패턴으로 scratch DB(dbname=ci)에 `prisma/init/tables.sql`(frontend)과
 * `alembic upgrade head`(public)를 실제 배포와 같은 순서로 적용한 뒤 이 테스트를 돌린다 —
 * 탈퇴 연쇄가 `public` 스키마의 워크스페이스 데이터도 지우므로 frontend 만 있는 DB 로는
 * 그 축을 검사할 수 없다 (#363).
 */
import { afterAll, describe, expect, it } from "vitest";
import { createHash, randomUUID } from "node:crypto";
import { prisma } from "@/lib/prisma/client";
import { Prisma } from "@/prisma/generated/client";
import {
  AUDIT_ANONYMIZED_TABLES,
  deletedUserAuditId,
  deleteUserCascade,
  emailVerificationOtpIdentifier,
  EMAIL_VERIFICATION_OTP_PREFIX,
  emailVerifiedGrantIdentifier,
  USER_SCOPED_IDENTIFIER_TABLES,
  USER_SCOPED_IDENTIFIER_TABLES_EXCLUDED,
  WORKSPACE_SCOPED_PUBLIC_TABLES,
  WORKSPACE_SCOPED_PUBLIC_TABLES_EXCLUDED,
} from "@/lib/auth/authUtils";

describe("deleteUserCascade — 소유 워크스페이스의 자식 행까지 지운다 (#357 리뷰 [A])", () => {
  it("워크스페이스에 메뉴·도메인이 붙어 있어도 탈퇴가 성공하고 자식 행도 함께 사라진다", async () => {
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    // ws-dbtest- (10자) + userId 앞 20자 = 정확히 30자 (workspace_code varchar(30) 상한).
    const workspaceCode = `ws-dbtest-${userId.slice(0, 20)}`;

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 개인 워크스페이스", is_personal: true },
      });
      // 실배포 형태 재현: seed.sql·0005_backfill_workspace_member 둘 다 tn_user.workspace_id 를
      // 채운다 — 픽스처에만 비워 두면 user.delete 를 뒤로 미루는 회귀가 P2003 을 못 낸다
      // (#357 3회차 재리뷰 [2]).
      await prisma.user.create({
        data: { id: userId, email, name: "dbtest-user", appr_at: "Y", use_at: "Y", workspace_id: workspace.id },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "owner" },
      });
      // 관리 UI 로 도달 가능한 구성을 재현한다 — 개인 워크스페이스도 목록에서 안 걸러지므로
      // 운영자가 메뉴·도메인을 붙일 수 있다
      // (app/api/common/system/workspace/[workspace_id]/menu, .../domain 라우트).
      await prisma.workspaceMenu.create({ data: { workspace_id: workspace.id, menu_id: "m-dbtest" } });
      await prisma.workspaceDomain.create({
        data: { domain: `dbtest-${userId.slice(0, 8)}.example.com`, workspace_id: workspace.id },
      });

      // 수정 전: 트랜잭션 배열의 마지막 workspace.deleteMany 가 FK 위반(P2003)으로 던지고
      // $transaction 배열 전체가 롤백되어 탈퇴 자체가 500 으로 실패했다. 여기서는
      // "던지지 않는다"가 곧 그 회귀의 검출이다.
      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const [menus, domains, remainingWorkspace, remainingUser] = await Promise.all([
        prisma.workspaceMenu.findMany({ where: { workspace_id: workspace.id } }),
        prisma.workspaceDomain.findMany({ where: { workspace_id: workspace.id } }),
        prisma.workspace.findUnique({ where: { id: workspace.id } }),
        prisma.user.findUnique({ where: { email } }),
      ]);
      expect(menus).toHaveLength(0);
      expect(domains).toHaveLength(0);
      expect(remainingWorkspace).toBeNull();
      expect(remainingUser).toBeNull();
    } finally {
      // 단정이 실패해도(=deleteUserCascade 가 여전히 깨져 있어도) 대상 DB(개발 DB 재사용 가능성
      // 포함)에 dbtest 잔여 행을 남기지 않는다. 존재하지 않는 행에 대한 deleteMany 는 0건
      // 삭제로 조용히 성공한다. 순서 주의: user.workspace_id 가 이 워크스페이스를 참조하므로
      // (NoAction) workspace 삭제 전에 user 를 먼저 지워야 한다 — 그 반대는 FK 위반.
      await prisma.workspaceMenu.deleteMany({ where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } } });
      await prisma.workspaceDomain.deleteMany({
        where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } },
      });
      await prisma.workspaceMember.deleteMany({ where: { user_id: userId } });
      await prisma.user.deleteMany({ where: { id: userId } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });

  it("공용(is_personal:false) 워크스페이스의 owner 를 지워도 그 워크스페이스와 메뉴·도메인은 남는다 (#357 재리뷰 차단급)", async () => {
    // 재현: seed.sql(:75, is_personal=false `acme`) · 0005_backfill_workspace_member 리비전이
    // owner 멤버십을 공용 워크스페이스에도 만든다 — "owner = 개인 워크스페이스 소유자" 는 거짓이다.
    // 앞 수정(#357 [A])이 ownedWorkspaceIds 조회에 is_personal 가드 없이 workspaceMenu/
    // workspaceDomain 을 지워, 공용 워크스페이스의 메뉴·도메인만 조용히 전멸시켰다(새 회귀).
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const workspaceCode = `ws-dbshr-${userId.slice(0, 21)}`; // 9자 + 21자 = 30자

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 공용 워크스페이스", is_personal: false },
      });
      // 실배포 형태 재현 (위 개인 워크스페이스 케이스와 동일 근거).
      await prisma.user.create({
        data: {
          id: userId,
          email,
          name: "dbtest-shared-owner",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "owner" },
      });
      await prisma.workspaceMenu.create({ data: { workspace_id: workspace.id, menu_id: "m-dbtest-shr" } });
      await prisma.workspaceDomain.create({
        data: { domain: `dbtest-shr-${userId.slice(0, 8)}.example.com`, workspace_id: workspace.id },
      });

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const [menus, domains, remainingWorkspace, remainingUser] = await Promise.all([
        prisma.workspaceMenu.findMany({ where: { workspace_id: workspace.id } }),
        prisma.workspaceDomain.findMany({ where: { workspace_id: workspace.id } }),
        prisma.workspace.findUnique({ where: { id: workspace.id } }),
        prisma.user.findUnique({ where: { email } }),
      ]);
      // 사용자 탈퇴는 정상 진행되지만, 공용 워크스페이스 자신과 그 자식(메뉴·도메인)은
      // 이 사용자 소유가 아니므로 손대면 안 된다.
      expect(menus).toHaveLength(1);
      expect(domains).toHaveLength(1);
      expect(remainingWorkspace).not.toBeNull();
      expect(remainingUser).toBeNull();
    } finally {
      // 순서 주의: user.workspace_id 가 이 워크스페이스를 참조하므로 workspace 삭제 전에 user 를
      // 먼저 지운다.
      await prisma.workspaceMenu.deleteMany({ where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } } });
      await prisma.workspaceDomain.deleteMany({
        where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } },
      });
      await prisma.workspaceMember.deleteMany({ where: { user_id: userId } });
      await prisma.user.deleteMany({ where: { id: userId } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });

  it("ba_session·ba_account·tn_author_member 자식 행도 함께 사라진다 (#357 재리뷰 비차단 — 그물 사각지대)", async () => {
    // 앞 그물(위 두 케이스)은 워크스페이스 축만 픽스처로 만들어 baSession.deleteMany ·
    // baAccount.deleteMany · authorMember.deleteMany 를 각각 지워도 빨강이 되지 않았다
    // (#357 재리뷰 뚫린 것 #4~#6). 세 축을 직접 심어 닫는다.
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const authorId = `at-dbtest-${userId.slice(0, 10)}`; // varchar(20) 상한
    // ws-dbchld- (10자) + userId 앞 20자 = 정확히 30자.
    const workspaceCode = `ws-dbchld-${userId.slice(0, 20)}`;

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 자식축 워크스페이스", is_personal: true },
      });
      // 실배포 형태 재현 (위 두 케이스와 동일 근거) — 이 축(session·account·authorMember)만
      // 노리는 테스트라도 workspace_id 가 비어 있으면 픽스처가 비현실적이다.
      await prisma.user.create({
        data: {
          id: userId,
          email,
          name: "dbtest-child-axes",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "owner" },
      });
      await prisma.baSession.create({
        data: {
          id: randomUUID(),
          expiresAt: new Date(Date.now() + 3600_000),
          token: randomUUID(),
          createdAt: new Date(),
          updatedAt: new Date(),
          userId,
        },
      });
      await prisma.baAccount.create({
        data: {
          id: randomUUID(),
          accountId: userId,
          providerId: "credential",
          userId,
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      });
      await prisma.author.create({ data: { author_id: authorId, author_nm: "dbtest 권한" } });
      await prisma.authorMember.create({ data: { author_id: authorId, user_id: email } });

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const [sessions, accounts, authorMembers, remainingWorkspace, remainingUser] = await Promise.all([
        prisma.baSession.findMany({ where: { userId } }),
        prisma.baAccount.findMany({ where: { userId } }),
        prisma.authorMember.findMany({ where: { author_id: authorId, user_id: email } }),
        prisma.workspace.findUnique({ where: { id: workspace.id } }),
        prisma.user.findUnique({ where: { email } }),
      ]);
      expect(sessions).toHaveLength(0);
      expect(accounts).toHaveLength(0);
      expect(authorMembers).toHaveLength(0);
      expect(remainingWorkspace).toBeNull();
      expect(remainingUser).toBeNull();
    } finally {
      // 순서 주의: user.workspace_id 가 이 워크스페이스를 참조하므로 workspace 삭제 전에 user 를
      // 먼저 지운다.
      await prisma.baSession.deleteMany({ where: { userId } });
      await prisma.baAccount.deleteMany({ where: { userId } });
      await prisma.authorMember.deleteMany({ where: { author_id: authorId } });
      await prisma.author.deleteMany({ where: { author_id: authorId } });
      await prisma.workspaceMember.deleteMany({ where: { user_id: userId } });
      await prisma.user.deleteMany({ where: { id: userId } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });

  it("role:member 로 남의 개인 워크스페이스에 속한 사용자를 지워도 그 워크스페이스는 소유로 오인되지 않는다 (#357 3회차 재리뷰 — role 술어 확대 축)", async () => {
    // 재현 경로: app/api/common/system/adminuser/route.ts:104,136 이 시스템관리자에게
    // workspace_id 를 is_personal 필터 없이 허용하고, syncDefaultWorkspaceMembership(…, "member", tx)
    // 로 role:"member" 멤버십을 만든다 — 타 사용자의 **개인** 워크스페이스에도 role:"member" 로
    // 속할 수 있다는 뜻이다. `ownedWorkspaceIds` 조회의 `role: "owner"` 를 `role: { in: ["owner",
    // "member"] }` 로 넓히면 이 멤버가 자기 것이 아닌 워크스페이스를 "소유"로 오인해 지우려
    // 든다 — 소유자 자신의 멤버십(role:owner)이 여전히 그 워크스페이스를 참조하므로
    // workspace.deleteMany 가 FK 위반(P2003)으로 던지고, 그 여파로 이 멤버 자신의 정상적인
    // 탈퇴까지 500 으로 실패한다(트랜잭션 전체 롤백). role 술어를 owner 로 좁혀야 이 사각지대가
    // 닫힌다.
    const ownerId = randomUUID();
    const ownerEmail = `${ownerId}@dbtest.example.com`;
    const memberId = randomUUID();
    const memberEmail = `${memberId}@dbtest.example.com`;
    // ws-dbown- (9자) + userId 앞 21자 = 정확히 30자.
    const workspaceCode = `ws-dbown-${ownerId.slice(0, 21)}`;

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 남의 개인 워크스페이스", is_personal: true },
      });
      await prisma.user.create({
        data: {
          id: ownerId,
          email: ownerEmail,
          name: "dbtest-real-owner",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: ownerId, role: "owner", is_default: true },
      });
      await prisma.workspaceMenu.create({ data: { workspace_id: workspace.id, menu_id: "m-dbtest-own" } });
      await prisma.workspaceDomain.create({
        data: { domain: `dbtest-own-${ownerId.slice(0, 8)}.example.com`, workspace_id: workspace.id },
      });

      // adminuser 라우트가 만드는 형태: 타 사용자를 이 개인 워크스페이스에 role:member 로 배정.
      await prisma.user.create({
        data: {
          id: memberId,
          email: memberEmail,
          name: "dbtest-outside-member",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: memberId, role: "member", is_default: true },
      });

      await expect(deleteUserCascade(memberEmail)).resolves.toBeUndefined();

      const [ownerMembership, memberMembership, menus, domains, remainingWorkspace, remainingOwner, remainingMember] =
        await Promise.all([
          prisma.workspaceMember.findUnique({
            where: { workspace_id_user_id: { workspace_id: workspace.id, user_id: ownerId } },
          }),
          prisma.workspaceMember.findUnique({
            where: { workspace_id_user_id: { workspace_id: workspace.id, user_id: memberId } },
          }),
          prisma.workspaceMenu.findMany({ where: { workspace_id: workspace.id } }),
          prisma.workspaceDomain.findMany({ where: { workspace_id: workspace.id } }),
          prisma.workspace.findUnique({ where: { id: workspace.id } }),
          prisma.user.findUnique({ where: { email: ownerEmail } }),
          prisma.user.findUnique({ where: { email: memberEmail } }),
        ]);
      // 지워진 건 member 자신의 소속뿐 — 워크스페이스·소유자·메뉴·도메인은 남의 것이라 무사해야 한다.
      expect(ownerMembership).not.toBeNull();
      expect(memberMembership).toBeNull();
      expect(menus).toHaveLength(1);
      expect(domains).toHaveLength(1);
      expect(remainingWorkspace).not.toBeNull();
      expect(remainingOwner).not.toBeNull();
      expect(remainingMember).toBeNull();
    } finally {
      // 순서 주의: 두 사용자의 workspace_id 가 이 워크스페이스를 참조하므로 workspace 삭제 전에
      // 둘 다 먼저 지운다.
      await prisma.workspaceMenu.deleteMany({ where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } } });
      await prisma.workspaceDomain.deleteMany({
        where: { workspace_id: { in: await workspaceIdsFor(workspaceCode) } },
      });
      await prisma.workspaceMember.deleteMany({ where: { user_id: { in: [ownerId, memberId] } } });
      await prisma.user.deleteMany({ where: { id: { in: [ownerId, memberId] } } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });
});

/**
 * `public` 스키마 픽스처 — 테이블마다 행 1건씩. 키를 `WORKSPACE_SCOPED_PUBLIC_TABLES` 의 원소
 * 타입으로 못 박아, **삭제 목록에 테이블을 더하면 여기 픽스처를 안 넣고는 타입 체크가 통과하지
 * 않게** 한다. 그물이 목록을 따라 자동으로 넓어지는 대신 조용히 비는 것을 막는다.
 */
const PUBLIC_FIXTURES: Record<
  (typeof WORKSPACE_SCOPED_PUBLIC_TABLES)[number],
  (ws: number, key: string) => Prisma.Sql
> = {
  // 백테스트 실행은 개인 실험 결과라 워크스페이스와 함께 지운다. 자산곡선·거래·신호·현금원장
  // 넷은 `run_id` FK 의 ON DELETE CASCADE 로 따라 지워지므로 여기서 따로 심지 않는다 —
  // 실제 Postgres 에서 확인했다(run 1건을 지우니 자식 넷이 1→0).
  tn_backtest_run: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_backtest_run
                 (workspace_id, strategy_key, strategy_version, period_from, period_to, initial_cash)
               VALUES (${ws}, ${`k-${key}`}, '1', '2026-01-01', '2026-02-01', 1000)`,
  // 봇은 워크스페이스 자산이라 워크스페이스와 함께 지운다. 실린 전략(`tn_bot_strategy`)은
  // `bot_id` FK 의 ON DELETE CASCADE 로 따라 지워지므로 여기서 따로 심지 않는다 (#150 B0).
  tn_bot: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_bot (workspace_id, bot_nm) VALUES (${ws}, ${`dbtest 봇 ${key}`})`,
  tn_holding: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_holding (workspace_id, portfolio_id, ticker, holding_nm)
                 VALUES (${ws}, ${`p-${key}`}, ${`T${key}`}, 'dbtest 보유종목')`,
  tn_nav: (ws) => Prisma.sql`INSERT INTO public.tn_nav (workspace_id, nav_dt, nav) VALUES (${ws}, now(), 100.0)`,
  tn_portfolio: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_portfolio (workspace_id, portfolio_id, portfolio_nm)
                 VALUES (${ws}, ${`p-${key}`}, 'dbtest 포트폴리오')`,
  tn_research_document: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_research_document (workspace_id, user_id, atch_file_id)
                 VALUES (${ws}, ${`${key}@dbtest.example.com`}, ${`f-${key}`})`,
  tn_scheduler: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_scheduler (scheduler_id, workspace_id, scheduler_nm)
                 VALUES (${`s-${key}`}, ${ws}, 'dbtest 스케줄러')`,
  tn_scheduler_member: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_scheduler_member (scheduler_id, workspace_id, account_id, email)
                 VALUES (${`s-${key}`}, ${ws}, ${`acct-${key}`}, ${`${key}@dbtest.example.com`})`,
  tn_watchlist: (ws, key) =>
    Prisma.sql`INSERT INTO public.tn_watchlist (workspace_id, ticker) VALUES (${ws}, ${`T${key}`})`,
};

async function seedWorkspaceScopedPublicRows(workspaceId: number, key: string): Promise<void> {
  for (const table of WORKSPACE_SCOPED_PUBLIC_TABLES) {
    await prisma.$executeRaw(PUBLIC_FIXTURES[table](workspaceId, key));
  }
}

/** 테이블별 잔여 행 수 — "합계 0" 이 아니라 어느 테이블이 안 지워졌는지 이름으로 드러나게 센다. */
async function countWorkspaceScopedPublicRows(workspaceId: number): Promise<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const table of WORKSPACE_SCOPED_PUBLIC_TABLES) {
    const rows = await prisma.$queryRaw<{ count: bigint }[]>(
      Prisma.sql`SELECT count(*) AS count FROM ${Prisma.raw(`public.${table}`)} WHERE workspace_id = ${workspaceId}`,
    );
    counts[table] = Number(rows[0].count);
  }
  return counts;
}

async function purgeWorkspaceScopedPublicRows(workspaceIds: number[]): Promise<void> {
  if (workspaceIds.length === 0) return;
  for (const table of WORKSPACE_SCOPED_PUBLIC_TABLES) {
    await prisma.$executeRaw(
      Prisma.sql`DELETE FROM ${Prisma.raw(`public.${table}`)} WHERE workspace_id IN (${Prisma.join(workspaceIds)})`,
    );
  }
}

describe("deleteUserCascade — FK 가 없어 조용히 남던 축 (#363)", () => {
  it("삭제 대상 목록이 비어 있지 않다 (그물이 0건을 훑고 초록이 되는 것을 막는다)", () => {
    expect(WORKSPACE_SCOPED_PUBLIC_TABLES.length).toBeGreaterThan(0);
    // 픽스처 누락으로 일부 테이블만 검사되는 상태를 런타임에서도 드러낸다 (타입 체크와 이중).
    expect(Object.keys(PUBLIC_FIXTURES).sort()).toEqual([...WORKSPACE_SCOPED_PUBLIC_TABLES].sort());
  });

  it("public 스키마의 workspace_id 보유 테이블이 삭제 목록 또는 제외 목록에 전부 들어 있다", async () => {
    // 목록을 손으로 유지하면 새 마이그레이션이 워크스페이스 종속 테이블을 더할 때 조용히
    // 어긋난다 — 실제 스키마를 원천으로 삼아 대조한다. 새 테이블이 생기면 여기서 빨강이 되고,
    // 사람이 "탈퇴 때 지울 것인가"를 판단해 둘 중 한 목록에 넣어야 한다.
    const rows = await prisma.$queryRaw<{ table_name: string }[]>`
      SELECT c.table_name FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
      WHERE c.table_schema = 'public' AND c.column_name = 'workspace_id'
    `;
    const found = rows.map((r) => r.table_name).sort();
    // 대상 DB 에 public 스키마가 안 세워졌으면 이 검사는 아무것도 안 본 것이다 — 통과시키지 않는다.
    expect(found.length).toBeGreaterThan(0);

    const accounted: string[] = [...WORKSPACE_SCOPED_PUBLIC_TABLES, ...WORKSPACE_SCOPED_PUBLIC_TABLES_EXCLUDED];
    expect(found.filter((table) => !accounted.includes(table))).toEqual([]);
  });

  it("탈퇴자 식별자(이메일·user id)를 담은 테이블이 삭제 목록 또는 제외 목록에 전부 들어 있다", async () => {
    // 워크스페이스 축(`workspace_id` 대조) 밖의 축이다 — 공용 워크스페이스만 쓰던 사용자의 행은
    // 워크스페이스 축 삭제로 하나도 안 지워지므로, 식별자 컬럼을 원천으로 따로 대조해야 한다.
    // `th_email_log.to` 가 정확히 이 사각지대에 있었다 (#363 리드 결정으로 삭제 목록에 편입).
    // `ba_verification.identifier` 도 같은 자리였다 (#3 리드 결정으로 편입).
    // 감사 컬럼(`reg_id`·`mod_id`)은 이 대조의 대상이 아니다 — 행의 주체가 아니라 조작한 사람을
    // 적는 자리라 처리가 삭제가 아니라 **익명화**다 (#3 ㉡, 2026-08-12 리드 결정). 그 축은 아래
    // "감사 컬럼 익명화" describe 의 전용 그물(AUDIT_ANONYMIZED_TABLES 양방향 완전 일치)이 맡는다
    // — 두 그물의 경계: 이 대조는 「행째 지울 테이블」, 저 대조는 「행은 남기고 값만 바꿀 컬럼」.
    const rows = await prisma.$queryRaw<{ table_schema: string; table_name: string; column_name: string }[]>`
      SELECT c.table_schema, c.table_name, c.column_name
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
      WHERE c.table_schema IN ('frontend', 'public')
        AND c.data_type IN ('character varying', 'text')
        AND c.column_name ~* '(email|mail|user_id|userid|account_id|identifier|^to$)'
    `;
    const found = [...new Set(rows.map((r) => `${r.table_schema}.${r.table_name}`))].sort();
    // 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있게 검사한 수를 남긴다.
    console.log(`[#3] 식별자 컬럼 대조: 테이블 ${found.length}개 / 컬럼 ${rows.length}개 검사`);
    // 대상 DB 에 스키마가 안 세워졌으면 이 검사는 아무것도 안 본 것이다 — 통과시키지 않는다.
    expect(found.length).toBeGreaterThan(0);
    expect(rows.length).toBeGreaterThan(0);
    expect(USER_SCOPED_IDENTIFIER_TABLES.length).toBeGreaterThan(0);

    const accounted: string[] = [...USER_SCOPED_IDENTIFIER_TABLES, ...USER_SCOPED_IDENTIFIER_TABLES_EXCLUDED];
    expect(found.filter((table) => !accounted.includes(table))).toEqual([]);
    // 반대 방향도 본다 — 삭제 목록의 테이블이 이 조회에 안 잡히면(컬럼명 규칙이 바뀌었거나 그
    // 테이블이 사라졌거나) 위 대조는 **아무것도 안 보고** 초록이 된다. 특히 `ba_verification` 은
    // `identifier` 라는 이름 하나로만 잡히므로 이름이 바뀌면 조용히 범위 밖이 된다.
    // (제외 목록은 이 검사에서 뺀다 — `public.workspace_doc_chunk` 는 doc-search 가 런타임에
    //  자가 DDL 로 만들어 CI 의 스키마에는 아예 없다. 그 근거는 authUtils.ts 의 주석에 있다.)
    expect(USER_SCOPED_IDENTIFIER_TABLES.filter((table) => !found.includes(table))).toEqual([]);
  });

  it("개인 워크스페이스의 public 스키마 데이터와 대화 이력이 테이블마다 0건이 된다", async () => {
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const key = userId.slice(0, 8);
    // ws-dbpub- (9자) + userId 앞 21자 = 정확히 30자.
    const workspaceCode = `ws-dbpub-${userId.slice(0, 21)}`;
    let workspaceId = -1;

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest public 축 워크스페이스", is_personal: true },
      });
      workspaceId = workspace.id;
      await prisma.user.create({
        data: { id: userId, email, name: "dbtest-public", appr_at: "Y", use_at: "Y", workspace_id: workspace.id },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "owner" },
      });
      await prisma.aiChatHistory.create({
        data: { email, gid: BigInt(Date.now()), sort: 1, question: "dbtest 질문", answer: "dbtest 답변" },
      });
      await seedWorkspaceScopedPublicRows(workspace.id, key);
      // 사용자 축(account_id = tn_user.id)으로 매달린 수신자 등록 — 워크스페이스 축과 별개다.
      await prisma.$executeRaw`INSERT INTO public.tn_scheduler_member (scheduler_id, workspace_id, account_id, email)
                               VALUES (${`s-u-${key}`}, ${workspace.id}, ${userId}, ${email})`;

      // 심은 것이 실제로 들어갔는지 먼저 확인한다 — 픽스처가 0건이면 "삭제 후 0건" 은 아무것도 증명하지 못한다.
      const before = await countWorkspaceScopedPublicRows(workspace.id);
      for (const table of WORKSPACE_SCOPED_PUBLIC_TABLES) {
        expect.soft(`${table}=${before[table]}`).not.toBe(`${table}=0`);
      }

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const after = await countWorkspaceScopedPublicRows(workspace.id);
      for (const table of WORKSPACE_SCOPED_PUBLIC_TABLES) {
        expect.soft(`${table}=${after[table]}`).toBe(`${table}=0`);
      }
      const [history, schedulerMemberByUser] = await Promise.all([
        prisma.aiChatHistory.findMany({ where: { email } }),
        prisma.$queryRaw<
          { count: bigint }[]
        >`SELECT count(*) AS count FROM public.tn_scheduler_member WHERE account_id = ${userId}`,
      ]);
      expect(history).toHaveLength(0);
      expect(Number(schedulerMemberByUser[0].count)).toBe(0);
    } finally {
      await purgeWorkspaceScopedPublicRows(workspaceId > 0 ? [workspaceId] : []);
      await prisma.$executeRaw`DELETE FROM public.tn_scheduler_member WHERE account_id = ${userId}`;
      await prisma.aiChatHistory.deleteMany({ where: { email } });
      await prisma.workspaceMember.deleteMany({ where: { user_id: userId } });
      await prisma.user.deleteMany({ where: { id: userId } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });

  it("소유 개인 워크스페이스가 없는(공용 워크스페이스만 쓰던) 사용자의 대화 이력·메일 로그도 지워진다", async () => {
    // 대화 이력·메일 발송 로그는 워크스페이스가 아니라 이메일에 매달려 있다 — 워크스페이스 축
    // 삭제 안에 끼워 넣으면 공용 워크스페이스만 쓰던 사용자의 것이 통째로 살아남는다.
    // `th_email_log.to` 는 2026-08-05 리드 결정(#363)으로 PII 취급해 지운다.
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const workspaceCode = `ws-dbshr2-${userId.slice(0, 20)}`;
    // 남의 로그 — 이메일 축 삭제가 넓게 쓸어가면 이 행이 사라져 빨강이 된다.
    const otherEmail = `other-${userId}@dbtest.example.com`;

    try {
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 공용 워크스페이스2", is_personal: false },
      });
      await prisma.user.create({
        data: {
          id: userId,
          email,
          name: "dbtest-shared-history",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "member", is_default: true },
      });
      await prisma.aiChatHistory.create({
        data: { email, gid: BigInt(Date.now()), sort: 1, question: "공용 사용자 질문", answer: "답변" },
      });
      await prisma.emailLog.createMany({
        data: [
          { to: email, subject: "dbtest 발송", status: "SUCCESS", reg_dt: new Date() },
          // 대소문자가 다른 과거 행 — `normalizeEmail` 규칙 이전에 쓰인 행까지 잡아야 한다.
          { to: email.toUpperCase(), subject: "dbtest 발송(대문자)", status: "SUCCESS", reg_dt: new Date() },
          { to: otherEmail, subject: "남의 발송", status: "SUCCESS", reg_dt: new Date() },
        ],
      });
      // 심은 것이 실제로 들어갔는지 먼저 확인한다 — 0건이면 "삭제 후 0건" 은 아무것도 증명하지 못한다.
      expect(await prisma.emailLog.count({ where: { to: { equals: email, mode: "insensitive" } } })).toBe(2);

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const history = await prisma.aiChatHistory.findMany({ where: { email } });
      expect(history).toHaveLength(0);
      expect(await prisma.emailLog.count({ where: { to: { equals: email, mode: "insensitive" } } })).toBe(0);
      // 남의 것(공용 워크스페이스·다른 수신자의 로그)은 그대로여야 한다.
      expect(await prisma.emailLog.count({ where: { to: otherEmail } })).toBe(1);
      expect(await prisma.workspace.findUnique({ where: { id: workspace.id } })).not.toBeNull();
    } finally {
      await prisma.emailLog.deleteMany({ where: { to: { in: [email, email.toUpperCase(), otherEmail] } } });
      await prisma.aiChatHistory.deleteMany({ where: { email } });
      await prisma.workspaceMember.deleteMany({ where: { user_id: userId } });
      await prisma.user.deleteMany({ where: { id: userId } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });
});

describe("deleteUserCascade — 인증 토큰(ba_verification)도 사용자 축에서 지운다 (#3 리드 결정)", () => {
  /** Better Auth 가 저장하는 모양 그대로 — `verification.storeIdentifier: "hashed"`(auth.ts) 의 기본 해시. */
  const hashedIdentifier = (raw: string) => createHash("sha256").update(raw).digest("base64url");

  it("탈퇴자의 OTP·재설정 토큰만 사라지고 남의 토큰과 이웃 이메일의 토큰은 그대로다", async () => {
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const otherId = randomUUID();
    const otherEmail = `other-${userId}@dbtest.example.com`;
    // 접두어 확장 함정 — 삭제가 완전일치가 아니라 `startsWith`/`LIKE '…%'` 로 바뀌는 순간
    // 이 행이 함께 지워진다. 실제로 도달 가능한 주소다(가입 전 OTP 는 사용자 없이 발급된다).
    const neighborEmail = `${email}.evil.example.com`;
    const resetToken = randomUUID();
    const otherResetToken = randomUUID();
    // ws-dbver- (9자) + userId 앞 21자 = 정확히 30자.
    const workspaceCode = `ws-dbver-${userId.slice(0, 21)}`;
    const identifiers = [
      emailVerificationOtpIdentifier(email),
      // 정규화 규칙 이전에 쓰인 대문자 행 — 대소문자 무관 비교가 아니면 PII 가 그대로 남는다.
      `${EMAIL_VERIFICATION_OTP_PREFIX}${email.toUpperCase()}`,
      emailVerificationOtpIdentifier(otherEmail),
      emailVerificationOtpIdentifier(neighborEmail),
      hashedIdentifier(`reset-password:${resetToken}`),
      hashedIdentifier(`reset-password:${otherResetToken}`),
      // OTP 통과 증거(#343) — OTP 와 접두어가 다른 세 번째 평문 키다.
      emailVerifiedGrantIdentifier(email),
      emailVerifiedGrantIdentifier(otherEmail),
      emailVerifiedGrantIdentifier(neighborEmail),
    ];

    try {
      // 두 사용자가 함께 쓰는 공용 워크스페이스 — 이 축은 워크스페이스와 무관하고, 개인
      // 워크스페이스로 두면 남은 사용자의 `tn_user.workspace_id` 가 그것을 참조해 FK 로 막힌다.
      const workspace = await prisma.workspace.create({
        data: { workspace_code: workspaceCode, workspace_nm: "dbtest 인증토큰 워크스페이스", is_personal: false },
      });
      await prisma.user.create({
        data: { id: userId, email, name: "dbtest-verification", appr_at: "Y", use_at: "Y", workspace_id: workspace.id },
      });
      await prisma.user.create({
        data: {
          id: otherId,
          email: otherEmail,
          name: "dbtest-verification-other",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "member", is_default: true },
      });
      const inOneHour = new Date(Date.now() + 3600_000);
      await prisma.baVerification.createMany({
        data: [
          // 탈퇴자의 가입 OTP (평문 identifier).
          { id: randomUUID(), identifier: identifiers[0], value: "hash:0", expiresAt: inOneHour },
          // 같은 탈퇴자의 대문자 레거시 행.
          { id: randomUUID(), identifier: identifiers[1], value: "hash:0", expiresAt: inOneHour },
          // 남의 OTP — 살아 있어야 한다.
          { id: randomUUID(), identifier: identifiers[2], value: "hash:0", expiresAt: inOneHour },
          // 이웃 주소(접두어 확장)의 아직 안 쓴 유효 OTP — 살아 있어야 한다.
          { id: randomUUID(), identifier: identifiers[3], value: "hash:0", expiresAt: inOneHour },
          // 탈퇴자의 비밀번호 재설정 토큰 — identifier 는 해시, value 가 tn_user.id 원문이다.
          { id: randomUUID(), identifier: identifiers[4], value: userId, expiresAt: inOneHour },
          // 남의 재설정 토큰 — 살아 있어야 한다.
          { id: randomUUID(), identifier: identifiers[5], value: otherId, expiresAt: inOneHour },
          // 탈퇴자의 OTP 통과 증거 (#343).
          { id: randomUUID(), identifier: identifiers[6], value: "grant-hash", expiresAt: inOneHour },
          // 남의 증거 — 살아 있어야 한다.
          { id: randomUUID(), identifier: identifiers[7], value: "grant-hash", expiresAt: inOneHour },
          // 이웃 주소(접두어 확장)의 증거 — 살아 있어야 한다.
          { id: randomUUID(), identifier: identifiers[8], value: "grant-hash", expiresAt: inOneHour },
        ],
      });

      // 심은 것이 실제로 들어갔는지 먼저 확인한다 — 0건이면 "삭제 후 0건" 은 아무것도 증명하지 못한다.
      expect(await prisma.baVerification.count({ where: { identifier: { in: identifiers } } })).toBe(9);

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      const remaining = (
        await prisma.baVerification.findMany({
          where: { identifier: { in: identifiers } },
          select: { identifier: true },
        })
      )
        .map((r) => r.identifier)
        .sort();
      // 지워진 것: 탈퇴자의 평문 OTP 2건(대소문자 변형 포함) + 재설정 토큰 1건 + 인증 증거 1건.
      // 남은 것: 남의 OTP·이웃 주소 OTP·남의 재설정 토큰·남의 증거·이웃 주소 증거.
      expect(remaining).toEqual(
        [identifiers[2], identifiers[3], identifiers[5], identifiers[7], identifiers[8]].sort(),
      );
    } finally {
      await prisma.baVerification.deleteMany({ where: { identifier: { in: identifiers } } });
      await prisma.workspaceMember.deleteMany({ where: { user_id: { in: [userId, otherId] } } });
      await prisma.user.deleteMany({ where: { id: { in: [userId, otherId] } } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });
});

/** 감사 컬럼에 이 이메일이 남은 행 수 — 테이블별로 세어 어느 테이블이 안 처리됐는지 이름으로 드러낸다. */
async function countAuditRowsFor(email: string): Promise<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const table of AUDIT_ANONYMIZED_TABLES) {
    const rows = await prisma.$queryRaw<{ count: bigint }[]>(
      Prisma.sql`SELECT count(*) AS count FROM ${Prisma.raw(table)}
                  WHERE lower(reg_id) = lower(${email}) OR lower(mod_id) = lower(${email})`,
    );
    counts[table] = Number(rows[0].count);
  }
  return counts;
}

describe("deleteUserCascade — 감사 컬럼(reg_id·mod_id)은 지우지 않고 익명화한다 (#3 ㉡, 2026-08-12 리드 결정)", () => {
  it("감사 컬럼을 가진 테이블이 익명화 목록과 양방향으로 완전히 일치한다", async () => {
    // 기존 두 그물(workspace_id·식별자 컬럼)은 「행째 지울 테이블」의 대조라 감사 컬럼을 의도적으로
    // 범위 밖에 뒀다. 이 축은 「행은 남기고 값만 바꿀 컬럼」이라 별도 그물이 필요하고, 제외 목록이
    // 없으므로(감사 컬럼이 있으면 예외 없이 익명화 대상) accounted 방식이 아니라 **완전 일치**로
    // 대조한다 — 감사 컬럼을 가진 테이블이 새로 생기면 빨강, 목록의 테이블이 사라져도 빨강.
    const rows = await prisma.$queryRaw<{ tbl: string }[]>`
      SELECT DISTINCT c.table_schema || '.' || c.table_name AS tbl
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
      WHERE c.table_schema IN ('frontend', 'public') AND c.column_name IN ('reg_id', 'mod_id')
    `;
    const found = rows.map((r) => r.tbl).sort();
    // 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 구분할 수 있게 검사한 수를 남긴다 — 0건이면 실패.
    console.log(`[#3] 감사 컬럼 대조: 테이블 ${found.length}개 검사`);
    expect(found.length).toBeGreaterThan(0);
    expect(AUDIT_ANONYMIZED_TABLES.length).toBeGreaterThan(0);
    expect(found).toEqual([...AUDIT_ANONYMIZED_TABLES].sort());
  });

  it("탈퇴자의 이메일만 deleted-user-<id> 로 바뀌고, 남의 값·같은 행의 남의 컬럼은 그대로다", async () => {
    const userId = randomUUID();
    const email = `${userId}@dbtest.example.com`;
    const survivorId = randomUUID();
    const survivorEmail = `survivor-${userId}@dbtest.example.com`;
    // 두 사용자가 함께 쓰는 공용 워크스페이스 — 탈퇴 후에도 남아, 남은 행의 감사 컬럼을 검증할 수 있다.
    const workspaceCode = `ws-dbaud-${userId.slice(0, 21)}`; // 9자 + 21자 = 30자
    const portfolioId = `p-aud-${userId.slice(0, 8)}`;
    const anonymized = deletedUserAuditId(userId);

    try {
      // 워크스페이스 행 자체가 검증 대상이다: reg_id 는 탈퇴자(대문자 레거시 변형), mod_id 는
      // 생존자 — 컬럼 단위 치환이면 reg_id 만 바뀌고 mod_id 는 그대로여야 한다.
      const workspace = await prisma.workspace.create({
        data: {
          workspace_code: workspaceCode,
          workspace_nm: "dbtest 감사컬럼 워크스페이스",
          is_personal: false,
          reg_id: email.toUpperCase(),
          mod_id: survivorEmail,
        },
      });
      await prisma.user.create({
        data: { id: userId, email, name: "dbtest-audit", appr_at: "Y", use_at: "Y", workspace_id: workspace.id },
      });
      // 생존자 행을 탈퇴자(관리자 역할)가 만든 상황 — 행은 남고 감사 컬럼만 익명화돼야 한다.
      await prisma.user.create({
        data: {
          id: survivorId,
          email: survivorEmail,
          name: "dbtest-audit-survivor",
          appr_at: "Y",
          use_at: "Y",
          workspace_id: workspace.id,
          reg_id: email,
          mod_id: email,
        },
      });
      await prisma.workspaceMember.create({
        data: { workspace_id: workspace.id, user_id: userId, role: "member", is_default: true },
      });
      // 생존자 자신의 감사 값 — 익명화가 남의 값을 쓸어가면 이 행이 바뀌어 빨강이 된다.
      await prisma.workspaceMember.create({
        data: {
          workspace_id: workspace.id,
          user_id: survivorId,
          role: "member",
          is_default: true,
          reg_id: survivorEmail,
          mod_id: survivorEmail,
        },
      });
      // public 스키마 축 — 공용 워크스페이스의 행이라 삭제 축에 안 걸리고 남는다.
      await prisma.$executeRaw`INSERT INTO public.tn_portfolio (workspace_id, portfolio_id, portfolio_nm, reg_id, mod_id)
                               VALUES (${workspace.id}, ${portfolioId}, 'dbtest 감사 포트폴리오', ${email}, ${email})`;

      // 심은 것이 실제로 들어갔는지 먼저 확인한다 — 0건이면 "처리 후 0건" 은 아무것도 증명하지 못한다.
      const before = await countAuditRowsFor(email);
      expect(before["frontend.tn_user"]).toBeGreaterThan(0);
      expect(before["frontend.tn_workspace"]).toBeGreaterThan(0);
      expect(before["public.tn_portfolio"]).toBeGreaterThan(0);

      await expect(deleteUserCascade(email)).resolves.toBeUndefined();

      // 전수 소거: 26개 테이블 어디에도 탈퇴자 이메일이 감사 컬럼에 남지 않는다.
      const after = await countAuditRowsFor(email);
      for (const table of AUDIT_ANONYMIZED_TABLES) {
        expect.soft(`${table}=${after[table]}`).toBe(`${table}=0`);
      }
      // 값 수준: 같은 사람의 행위는 같은 값으로 묶이고, NULL 이 아니며, 같은 행의 남의 컬럼은 그대로다.
      const survivorRow = await prisma.user.findUniqueOrThrow({
        where: { id: survivorId },
        select: { reg_id: true, mod_id: true },
      });
      expect(survivorRow.reg_id).toBe(anonymized);
      expect(survivorRow.mod_id).toBe(anonymized);
      const workspaceRow = await prisma.workspace.findUniqueOrThrow({
        where: { id: workspace.id },
        select: { reg_id: true, mod_id: true },
      });
      expect(workspaceRow.reg_id).toBe(anonymized); // 대문자 레거시 변형도 잡는다
      expect(workspaceRow.mod_id).toBe(survivorEmail); // 같은 행이라도 남의 컬럼은 불변
      const portfolioRow = await prisma.$queryRaw<{ reg_id: string; mod_id: string }[]>`
        SELECT reg_id, mod_id FROM public.tn_portfolio WHERE portfolio_id = ${portfolioId}`;
      expect(portfolioRow[0]).toEqual({ reg_id: anonymized, mod_id: anonymized });
      // 생존자 자신의 감사 값은 안 건드렸다 — 「대상을 잘못 고르지 않았다」의 증명.
      const survivorMembership = await prisma.workspaceMember.findUniqueOrThrow({
        where: { workspace_id_user_id: { workspace_id: workspace.id, user_id: survivorId } },
        select: { reg_id: true, mod_id: true },
      });
      expect(survivorMembership).toEqual({ reg_id: survivorEmail, mod_id: survivorEmail });
    } finally {
      await prisma.$executeRaw`DELETE FROM public.tn_portfolio WHERE portfolio_id = ${portfolioId}`;
      await prisma.workspaceMember.deleteMany({ where: { user_id: { in: [userId, survivorId] } } });
      await prisma.user.deleteMany({ where: { id: { in: [userId, survivorId] } } });
      await prisma.workspace.deleteMany({ where: { workspace_code: workspaceCode } });
    }
  });
});

async function workspaceIdsFor(workspaceCode: string): Promise<number[]> {
  const rows = await prisma.workspace.findMany({ where: { workspace_code: workspaceCode }, select: { id: true } });
  return rows.map((r) => r.id);
}

afterAll(async () => {
  await prisma.$disconnect();
});
