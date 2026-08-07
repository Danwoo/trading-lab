/**
 * #362 회귀 그물 — **남의 개인 워크스페이스로 사용자를 배정할 수 있는가**를 실제 라우트 핸들러 +
 * 실제 Postgres 로 검사한다.
 *
 * 왜 mock 이 아니라 DB 인가: 이 결함의 피해는 "배정이 된다"에서 끝나지 않고 **그 워크스페이스
 * 소유자의 탈퇴가 통째로 500 이 되는 것**까지다(`deleteUserCascade` 의 `workspace.deleteMany` 가
 * FK 위반으로 던진다). 그 연쇄는 실제 FK 가 있는 DB 에서만 재현된다 — prisma 를 mock 하면
 * 그물이 "라우트가 거절 메시지를 만든다"까지만 보게 되고, 정작 지키려는 성질(소유자가 탈퇴할 수
 * 있다)은 검사되지 않는다.
 *
 * 배정 경로는 둘이고 둘 다 본다:
 * - 생성(POST `/api/common/system/adminuser`) — 이슈가 지목한 자리. Better Auth 의 `signUpEmail`
 *   을 물고 있어 라우트 핸들러 전체를 부르는 대신, 그 라우트가 쓰는 경계 검증
 *   `assertAssignableWorkspace` 를 실제 DB 로 직접 검사한다.
 * - 수정(PUT `/api/common/system/adminuser/[email]`) — 전수 조사에서 나온 같은 클래스의 자리.
 *   이쪽은 라우트 핸들러를 그대로 호출해 **기존 사용자 탈취 → 소유자 탈퇴 500** 까지 재현한다.
 *
 * 실행 전제·방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단과 같다 (`npm run test:db`).
 *
 * 파일 아래쪽에 **#413 F1**(값이 손상된 `workspace_id`) 그물이 같은 픽스처 위에 얹혀 있다 —
 * 같은 필드·같은 라우트의 한 단계 앞(값의 정체가 아니라 값이 숫자로 읽히는가) 경계다.
 */
import { afterAll, describe, expect, it, vi } from "vitest";
import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { assertAssignableWorkspace, deleteUserCascade } from "@/lib/auth/authUtils";
import { DEFAULT_USER_AUTHOR_ID, GENERAL_ADMIN_AUTHOR_ID } from "@/constants/protected";

// withAuth 가 부르는 세션만 대역으로 세운다 — 검증 대상(authUtils·prisma)은 진짜를 쓴다.
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("@/lib/auth/auth", () => ({
  auth: {
    api: {
      getSession: vi.fn(async () => ({
        response: {
          user: { id: "sysadmin-test", email: "sysadmin@dbtest.example.com" },
          // SYS_ADMIN_AUTHOR_ID — 이 결함은 시스템관리자만 도달할 수 있는 자리다.
          session: { authorId: "admin", workspaceId: null },
        },
        headers: new Headers(),
      })),
    },
  },
}));

const { PUT } = await import("@/app/api/common/system/adminuser/[email]/route");

type Fixture = {
  victimId: string;
  victimEmail: string;
  victimWorkspaceId: number;
  victimWorkspaceCode: string;
  targetId: string;
  targetEmail: string;
  sharedWorkspaceId: number;
  sharedWorkspaceCode: string;
};

/** 피해자(개인 워크스페이스 소유자)와 공격 대상(다른 워크스페이스의 기존 사용자)을 만든다. */
async function createFixture(): Promise<Fixture> {
  const victimId = randomUUID();
  const targetId = randomUUID();
  const victimWorkspaceCode = `ws-362v-${victimId.slice(0, 22)}`;
  const sharedWorkspaceCode = `ws-362s-${targetId.slice(0, 22)}`;

  // 워크스페이스를 옮기면 PUT 핸들러가 일반사용자 권한을 부여한다 — 그 권한 행이 없으면
  // 정상 경로가 FK 위반으로 죽어, 검증이 정상 배정까지 막았는지 아닌지 구분할 수 없게 된다.
  // (seed.sql 이 심는 행이지만 이 테스트 DB 는 tables.sql 만 적용된 빈 스키마다.)
  await prisma.author.upsert({
    where: { author_id: DEFAULT_USER_AUTHOR_ID },
    create: { author_id: DEFAULT_USER_AUTHOR_ID, author_nm: "일반사용자" },
    update: {},
  });

  const victimWorkspace = await prisma.workspace.create({
    data: { workspace_code: victimWorkspaceCode, workspace_nm: "362 피해자 개인 워크스페이스", is_personal: true },
  });
  const sharedWorkspace = await prisma.workspace.create({
    data: { workspace_code: sharedWorkspaceCode, workspace_nm: "362 공용 워크스페이스", is_personal: false },
  });

  const victimEmail = `${victimId}@dbtest.example.com`;
  const targetEmail = `${targetId}@dbtest.example.com`;

  await prisma.user.create({
    data: {
      id: victimId,
      email: victimEmail,
      name: "362-victim",
      appr_at: "Y",
      use_at: "Y",
      workspace_id: victimWorkspace.id,
    },
  });
  await prisma.workspaceMember.create({
    data: { workspace_id: victimWorkspace.id, user_id: victimId, role: "owner", is_default: true },
  });
  await prisma.user.create({
    data: {
      id: targetId,
      email: targetEmail,
      name: "362-target",
      appr_at: "Y",
      use_at: "Y",
      workspace_id: sharedWorkspace.id,
    },
  });
  await prisma.workspaceMember.create({
    data: { workspace_id: sharedWorkspace.id, user_id: targetId, role: "member", is_default: true },
  });

  return {
    victimId,
    victimEmail,
    victimWorkspaceId: victimWorkspace.id,
    victimWorkspaceCode,
    targetId,
    targetEmail,
    sharedWorkspaceId: sharedWorkspace.id,
    sharedWorkspaceCode,
  };
}

async function cleanupFixture(f: Fixture): Promise<void> {
  // 결함이 되살아난 상태(가드 없음)에서는 PUT 이 성공해 권한 행까지 만든다 — 그 행을 안 지우면
  // 정리가 FK 위반으로 죽어 정작 보려던 단정 실패가 가려진다.
  await prisma.authorMember.deleteMany({ where: { user_id: { in: [f.victimEmail, f.targetEmail] } } });
  await prisma.workspaceMember.deleteMany({ where: { user_id: { in: [f.victimId, f.targetId] } } });
  await prisma.user.deleteMany({ where: { id: { in: [f.victimId, f.targetId] } } });
  await prisma.workspace.deleteMany({
    where: { workspace_code: { in: [f.victimWorkspaceCode, f.sharedWorkspaceCode] } },
  });
}

function putRequest(
  email: string,
  body: Record<string, unknown>,
): [NextRequest, { params: Promise<{ email: string }> }] {
  const request = new NextRequest(`http://localhost/api/common/system/adminuser/${encodeURIComponent(email)}`, {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
  return [request, { params: Promise.resolve({ email }) }];
}

describe("#362 — 클라이언트가 보낸 workspace_id 의 경계 검증", () => {
  it("개인 워크스페이스는 배정 대상이 아니다 (생성 라우트가 쓰는 경계 검증)", async () => {
    const f = await createFixture();
    try {
      // 드롭다운(workspace/options)이 주는 값 = 활성 공용 워크스페이스 → 통과
      expect(await assertAssignableWorkspace(f.sharedWorkspaceId)).toBeNull();
      // 드롭다운에 없는 값 = 남의 개인 워크스페이스 → 거부
      expect(await assertAssignableWorkspace(f.victimWorkspaceId)).toBe("배정할 수 없는 워크스페이스입니다.");
      // 존재하지 않는 워크스페이스도 거부한다 — 예전에는 FK 위반 500 으로 새어 나갔다.
      expect(await assertAssignableWorkspace(-1)).toBe("배정할 수 없는 워크스페이스입니다.");
      // 미배정(null)은 정상 상태라 허용한다.
      expect(await assertAssignableWorkspace(null)).toBeNull();
    } finally {
      await cleanupFixture(f);
    }
  });

  it("Prisma 필터 객체를 넣어도 '아무 워크스페이스나' 로 통과하지 않는다 (#400 코멘트)", async () => {
    // 타입은 `number | null | undefined` 지만 값은 요청 본문에서 온 any 다. 필터 객체를 넣으면
    // `where.id` 가 동등 비교에서 범위 필터로 바뀌어, 존재 확인이 "요청한 그 워크스페이스"가
    // 아니라 "조건에 맞는 아무 워크스페이스"를 찾았다 (개발 DB 실측: {gt:0}·{not:-1} 둘 다 허용).
    const f = await createFixture();
    try {
      for (const payload of [{ gt: 0 }, { not: -1 }, { in: [f.sharedWorkspaceId] }, "1", 1.5]) {
        expect
          .soft(await assertAssignableWorkspace(payload as any), `payload=${JSON.stringify(payload)}`)
          .toBe("배정할 수 없는 워크스페이스입니다.");
      }
      // 대조 — 정상 스칼라는 여전히 통과한다.
      expect(await assertAssignableWorkspace(f.sharedWorkspaceId)).toBeNull();
    } finally {
      await cleanupFixture(f);
    }
  });

  it("수정 라우트에 남의 개인 워크스페이스 id 를 넣으면 거부되고, 소유자는 정상 탈퇴한다", async () => {
    const f = await createFixture();
    try {
      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id: f.victimWorkspaceId, // ← 공격 페이로드: 피해자의 개인 워크스페이스
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(400);
      expect(await response.json()).toEqual({ message: "배정할 수 없는 워크스페이스입니다." });

      // 탈취가 실제로 막혔는지 DB 로 확인한다 — 응답 문구만 보면 "거절 메시지는 나오는데 쓰기는
      // 이미 끝났다" 는 형태를 못 잡는다.
      const target = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(target?.workspace_id).toBe(f.sharedWorkspaceId);
      const intruderMembership = await prisma.workspaceMember.findUnique({
        where: { workspace_id_user_id: { workspace_id: f.victimWorkspaceId, user_id: f.targetId } },
      });
      expect(intruderMembership).toBeNull();

      // 그리고 이 결함의 진짜 피해였던 것: 소유자의 탈퇴가 성공한다.
      await expect(deleteUserCascade(f.victimEmail)).resolves.toBeUndefined();
      expect(await prisma.workspace.findUnique({ where: { id: f.victimWorkspaceId } })).toBeNull();
    } finally {
      await cleanupFixture(f);
    }
  });

  it("정상 배정(활성 공용 워크스페이스)은 그대로 통과한다", async () => {
    // 검증을 넣다가 정상 경로까지 막으면 그게 더 큰 사고다 — 반대 방향도 함께 고정한다.
    const f = await createFixture();
    const anotherCode = `ws-362o-${randomUUID().slice(0, 22)}`;
    try {
      const another = await prisma.workspace.create({
        data: { workspace_code: anotherCode, workspace_nm: "362 다른 공용 워크스페이스", is_personal: false },
      });
      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id: another.id,
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(200);
      const moved = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(moved?.workspace_id).toBe(another.id);
    } finally {
      await prisma.workspaceMember.deleteMany({ where: { user_id: { in: [f.victimId, f.targetId] } } });
      await prisma.authorMember.deleteMany({ where: { user_id: f.targetEmail } });
      await prisma.user.deleteMany({ where: { id: { in: [f.victimId, f.targetId] } } });
      await prisma.workspace.deleteMany({
        where: { workspace_code: { in: [f.victimWorkspaceCode, f.sharedWorkspaceCode, anotherCode] } },
      });
    }
  });
});

// ── 값이 손상된 workspace_id (PR #413 리뷰 F1) ───────────────────────────
//
// 위 `#362` 그물은 **값의 정체**(남의 개인 워크스페이스인가)를 본다. 이 그물은 그 앞 단계,
// **값이 숫자로 읽히는가**를 본다 — `workspace_id` 는 설계상 `Optional(int())`(null 이 정상
// 상태)라 `use_at`·`appr_at` 처럼 필수화해서 막을 수 없고, 그래서 #400 의 PUT 전체표현
// 계약이 이 필드엔 처음부터 걸리지 않았다.
//
// 결함이 있을 때: `Optional()` 이 변환 실패를 `undefined` 로 접고 `data.workspace_id ?? null`
// 이 그걸 명시적 null 로 흡수해 **200 + 배정 해제 + 일반관리자 권한 삭제 + 세션 무효화**.
// `"3e2"` 는 더 나쁘다 — 해제가 아니라 존재하지도 않을 300번 워크스페이스로 조용히 배정된다.
//
// mock 이 아니라 DB 로 보는 이유: 피해는 "update data 에 null 이 실린다"가 아니라 **권한 행이
// 실제로 사라진다**는 것이다. 그 연쇄(`authorMember.deleteMany` + `create`)는 실제 행이 있어야
// 재현된다.
describe("#413 F1 — 손상된 workspace_id 가 배정을 지우지 못한다", () => {
  // 「숫자로 아예 안 읽히는」 축 — 예전엔 `undefined` 로 접혀 배정 해제였다.
  // 「숫자로는 읽히는데 사람이 안 쓴 표기」 축은 아래 별도 케이스가 본다: 여기에 `"3e2"` 를
  // 넣어도 300번 워크스페이스가 없어 `assertAssignableWorkspace` 가 어차피 400 을 내므로,
  // 가드를 되돌려도 빨개지지 않는다(= 지탱하는 게 없는 케이스).
  const CORRUPTED: [string, unknown][] = [
    ["숫자로 안 읽히는 문자열", "garbage"],
    ["공백이 섞인 문자열", "1 2"],
    ["숫자 구분자 표기", "1_000"],
    ["빈 배열", []],
  ];

  it.each(CORRUPTED)("workspace_id 가 %s 이면 400 이고 DB 가 그대로다", async (_label, workspace_id) => {
    const f = await createFixture();
    try {
      await prisma.author.upsert({
        where: { author_id: GENERAL_ADMIN_AUTHOR_ID },
        create: { author_id: GENERAL_ADMIN_AUTHOR_ID, author_nm: "일반관리자" },
        update: {},
      });
      await prisma.authorMember.create({
        data: { author_id: GENERAL_ADMIN_AUTHOR_ID, user_id: f.targetEmail },
      });

      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id,
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(400);

      // 응답 문구만 보면 "거절은 하는데 쓰기는 이미 끝났다"를 못 잡는다 — 세 축을 다 본다.
      const after = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(after?.workspace_id, "배정이 해제됐다").toBe(f.sharedWorkspaceId);
      expect(
        await prisma.authorMember.count({ where: { user_id: f.targetEmail, author_id: GENERAL_ADMIN_AUTHOR_ID } }),
        "일반관리자 권한이 삭제됐다",
      ).toBe(1);
      expect(
        await prisma.authorMember.count({ where: { user_id: f.targetEmail, author_id: DEFAULT_USER_AUTHOR_ID } }),
        "일반사용자 권한이 새로 부여됐다",
      ).toBe(0);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("손상값 표가 줄지 않았다 (fail-closed)", () => {
    expect(CORRUPTED.length).toBe(4);
  });

  // 「숫자로는 읽히는데 사람이 안 쓴 표기」 축을 **실재하는 워크스페이스**로 재현한다.
  // `Number()` 는 16진수·지수 표기를 받고 정수 가드(`Number.isInteger`)도 통과하므로,
  // 결함이 있을 때 이 요청은 400 이 아니라 **사용자가 이름을 대지도 않은 워크스페이스로의
  // 실제 이동**이 된다. id 를 그 표기로 직접 만들어 "우연히 존재하지 않아서 막혔다"를 지운다.
  it.each([
    ["16진수", (id: number) => `0x${id.toString(16)}`],
    ["지수", (id: number) => `${id}e0`],
  ])("%s 표기로 실재하는 워크스페이스에 배정되지 않는다", async (_label, notate) => {
    const f = await createFixture();
    const anotherCode = `ws-413n-${randomUUID().slice(0, 22)}`;
    try {
      const another = await prisma.workspace.create({
        data: { workspace_code: anotherCode, workspace_nm: "413 다른 공용 워크스페이스", is_personal: false },
      });
      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id: notate(another.id),
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(400);
      const after = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(after?.workspace_id, "이름을 대지 않은 워크스페이스로 이동했다").toBe(f.sharedWorkspaceId);
    } finally {
      await cleanupFixture(f);
      await prisma.workspace.deleteMany({ where: { workspace_code: anotherCode } });
    }
  });

  // 거절이 정상 경로를 갉아먹지 않는지 — 화면이 실제로 보내는 형태(SelectBox 는 숫자 id,
  // clear 버튼은 null)와 그 문자열 표기까지 실제 DB 로 확인한다.
  it.each([
    ["숫자 (SelectBox 선택)", (f: Fixture) => f.sharedWorkspaceId],
    ["십진수 문자열", (f: Fixture) => String(f.sharedWorkspaceId)],
  ])("workspace_id 가 %s 이면 200 이고 배정이 유지된다", async (_label, pick) => {
    const f = await createFixture();
    try {
      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id: pick(f),
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(200);
      const after = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(after?.workspace_id).toBe(f.sharedWorkspaceId);
    } finally {
      await cleanupFixture(f);
    }
  });

  it("명시적 null 은 여전히 배정 해제다 (#400 전체표현 계약 — 손상값과 구분된다)", async () => {
    const f = await createFixture();
    try {
      const [request, ctx] = putRequest(f.targetEmail, {
        name: "362-target",
        dept: null,
        use_at: "Y",
        appr_at: "Y",
        workspace_id: null,
      });
      const response = await PUT(request, ctx);

      expect(response.status).toBe(200);
      const after = await prisma.user.findUnique({ where: { email: f.targetEmail } });
      expect(after?.workspace_id).toBeNull();
    } finally {
      await cleanupFixture(f);
    }
  });
});

afterAll(async () => {
  await prisma.$disconnect();
});
