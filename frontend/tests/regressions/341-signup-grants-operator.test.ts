// #341 — 가입이 배정하는 역할. 리드 결정 2026-08-23: **가입자는 자기 워크스페이스의 operator 다.**
// 결정 보완 2026-08-24: 그 전제가 서지 않는 갈래 — 이메일 도메인이 **남의 공용 워크스페이스**에
// 매핑돼 그리로 들어간 가입 — 는 초대받은 손님이라 게스트를 준다.
//
// **불변식 둘**:
// - 개인 워크스페이스를 받은 가입 → `tn_author_member` 의 `author_id` 는 쓰기가 열리는 역할
//   (`WRITE_AUTHOR_IDS`)이다. 게스트를 배정하면 그 계정은 실험대·시세·관심종목의 저장·실행이
//   **전부 403** 이 된다 — 이 이슈의 원래 증상이다.
// - 공용 워크스페이스로 들어간 가입 → `GUEST_AUTHOR_ID`. 운영자를 주면 초대 없이 남의
//   워크스페이스의 쓰기와 사용자관리(같은 워크스페이스 계정의 수정·삭제)가 열린다 —
//   PR #370 독립 리뷰가 잡은 갈래다.
//
// 값을 `"operator"` 리터럴로만 적지 않고 `WRITE_AUTHOR_IDS` 로도 판정하는 이유: 이 그물이 지키는
// 것은 특정 문자열이 아니라 「가입이 주는 역할로 쓰기가 열리는가」라는 성질이다. 역할 이름이
// 바뀌어도 성질이 유지되면 초록이고, 배정을 게스트로 되돌리면 이름과 무관하게 빨간불이다.
//
// **검증 경계** — prisma·better-auth 는 mock 이다(#343 과 같은 하네스). 여기서 보는 것은 라우트가
// **어떤 값으로 권한 행을 만드는가** 하나다. 실제 DB 반영은 로컬 스택 재현이 따로 확인한다.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/env", () => ({ env: { NODE_ENV: "development", EDITION: "saas" } }));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

const signUpEmail = vi.fn(async ({ body }: any) => ({ user: { id: "new-user", email: body.email } }));
vi.mock("@/lib/auth/auth", () => ({ auth: { api: { signUpEmail } } }));

/** `ba_verification` 을 대신하는 인메모리 저장소 — 증거 발급·소비는 진짜 코드가 돈다 (#343). */
type Row = { id: string; identifier: string; value: string; expiresAt: Date };
const verificationRows: Row[] = [];

/** 트랜잭션 안에서 만들어진 권한 행 — 이 배열이 이 테스트의 관측 지점이다. */
const grantedRoles: string[] = [];
/** 트랜잭션 안에서 사용자 행에 박힌 workspace_id — 어느 갈래(개인/공용)를 지났는지 여기서 확인한다. */
const assignedWorkspaceIds: Array<number | null> = [];
/** 도메인 매핑 대역 — `null` 이면 매핑 없음(개인 워크스페이스), 숫자면 그 공용 워크스페이스로 들어간다. */
let mappedWorkspaceId: number | null = null;
const PERSONAL_WORKSPACE_ID = 77;

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(async (args: any) => (args?.where?.id ? { id: "new-user" } : null)),
      update: vi.fn(async () => ({})),
    },
    baVerification: {
      findFirst: vi.fn(
        async (args: any) => verificationRows.find((r) => r.identifier === args.where.identifier) ?? null,
      ),
      create: vi.fn(async (args: any) => {
        verificationRows.push(args.data);
        return args.data;
      }),
      deleteMany: vi.fn(async (args: any) => {
        const match = (r: Row) => (args.where.id ? r.id === args.where.id : r.identifier === args.where.identifier);
        const kept = verificationRows.filter((r) => !match(r));
        const count = verificationRows.length - kept.length;
        verificationRows.splice(0, verificationRows.length, ...kept);
        return { count };
      }),
      delete: vi.fn(async (args: any) => {
        const i = verificationRows.findIndex((r) => r.id === args.where.id);
        return i < 0 ? null : verificationRows.splice(i, 1)[0];
      }),
      update: vi.fn(async (args: any) => {
        const row = verificationRows.find((r) => r.id === args.where.id);
        if (row) Object.assign(row, args.data);
        return row;
      }),
    },
    workspaceDomain: {
      findFirst: vi.fn(async () => (mappedWorkspaceId === null ? null : { workspace_id: mappedWorkspaceId })),
    },
    authorMember: { create: vi.fn(async () => ({})) },
    $transaction: vi.fn(async (fn: any) =>
      fn({
        user: {
          update: vi.fn(async (args: any) => {
            assignedWorkspaceIds.push(args?.data?.workspace_id ?? null);
            return {};
          }),
        },
        authorMember: {
          // 새 계정이라 기존 권한 행이 없다 — `grantDefaultAuthor` 가 「이미 있나」를 먼저 센다 (#355).
          count: vi.fn(async () => 0),
          create: vi.fn(async (args: any) => {
            grantedRoles.push(args?.data?.author_id);
            return {};
          }),
        },
      }),
    ),
  },
}));

vi.mock("@/lib/auth/authUtils", () => ({
  normalizeEmail: (e: string) => e.trim().toLowerCase(),
  emailVerificationOtpIdentifier: (e: string) => `email-verification-otp-${e.trim().toLowerCase()}`,
  ensurePersonalWorkspace: vi.fn(async () => PERSONAL_WORKSPACE_ID),
  syncDefaultWorkspaceMembership: vi.fn(async () => undefined),
  resolveOemSharedWorkspace: vi.fn(async () => ({ id: 1 })),
  deleteHalfCreatedUser: vi.fn(async () => undefined),
}));

const EMAIL = "signup341@example.com";
const BASE = { email: EMAIL, password: "abcd1234!", name: "새내기", dept: "개발팀" };

/** OTP 검증 라우트가 하는 일과 같다 — 인증 증거를 발급하고 원문 토큰을 돌려준다 (#343). */
async function issueGrant(): Promise<string> {
  const { issueSignupVerificationGrant } = await import("@/lib/auth/signupVerificationGrant");
  return issueSignupVerificationGrant(EMAIL);
}

async function signup(): Promise<Response> {
  const mod: any = await import("@/app/api/common/signup/route");
  return (await mod.POST(
    new NextRequest("http://localhost/api/common/signup", {
      method: "POST",
      body: JSON.stringify({ ...BASE, verificationToken: await issueGrant() }),
      headers: { "content-type": "application/json" },
    }),
  )) as Response;
}

beforeEach(() => {
  verificationRows.length = 0;
  grantedRoles.length = 0;
  assignedWorkspaceIds.length = 0;
  mappedWorkspaceId = null;
  signUpEmail.mockClear();
});

describe("#341 가입이 배정하는 역할", () => {
  it("정상 가입은 권한 행을 정확히 1건 만든다", async () => {
    const res = await signup();
    expect(res.status, "가입이 200 이 아니다 — 아래 단정들이 볼 것이 없어진다").toBe(200);
    expect(await res.json()).toMatchObject({ result: true });
    expect(grantedRoles, "가입이 권한 행을 만들지 않았다 — 계정이 메뉴도 못 본다").toHaveLength(1);
  });

  it("그 역할로 저장·실행이 열린다 (게스트가 아니다)", async () => {
    const { WRITE_AUTHOR_IDS } = await import("@/constants/writeAccess");
    const { GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID } = await import("@/constants/protected");

    await signup();

    expect(WRITE_AUTHOR_IDS.length, "쓰기가 열리는 역할이 0건이다 — 대조할 것이 없다").toBeGreaterThan(0);
    expect(grantedRoles[0], `가입이 준 역할(${grantedRoles[0]})로는 쓰기가 안 열린다`).toBeOneOf([...WRITE_AUTHOR_IDS]);
    expect(grantedRoles[0], "가입이 읽기전용 게스트를 배정했다 — #341 의 원래 증상").not.toBe(GUEST_AUTHOR_ID);
    expect(grantedRoles[0]).toBe(SIGNUP_AUTHOR_ID);
    // 위 단정이 「개인 워크스페이스 갈래」에서 나온 것임을 같이 못 박는다 — 아니면 아래 케이스와
    // 같은 경로를 두 번 재는 셈이다.
    expect(assignedWorkspaceIds, "가입이 사용자 행을 한 번 갱신해야 한다").toEqual([PERSONAL_WORKSPACE_ID]);
  });
});

describe("#341 결정 보완 — 도메인이 남의 공용 워크스페이스에 매핑된 가입", () => {
  const SHARED_WORKSPACE_ID = 1;

  it("그 워크스페이스로 들어가되 역할은 게스트다 — 초대 없이 남의 공간의 운영자가 되지 않는다", async () => {
    const { WRITE_AUTHOR_IDS } = await import("@/constants/writeAccess");
    const { GUEST_AUTHOR_ID } = await import("@/constants/protected");
    mappedWorkspaceId = SHARED_WORKSPACE_ID;

    const res = await signup();
    expect(res.status, "가입이 200 이 아니다 — 아래 단정들이 볼 것이 없어진다").toBe(200);

    // 매핑 경로를 실제로 지났는가 — 공용 워크스페이스가 배정돼야 이 케이스가 뜻을 갖는다.
    expect(assignedWorkspaceIds, "도메인 매핑이 공용 워크스페이스를 배정하지 않았다").toEqual([SHARED_WORKSPACE_ID]);

    expect(grantedRoles, "가입이 권한 행을 만들지 않았다 — 계정이 메뉴도 못 본다").toHaveLength(1);
    expect(
      grantedRoles[0],
      "남의 공용 워크스페이스로 들어간 가입에 운영자를 줬다 — 그 워크스페이스의 쓰기와 사용자관리가 초대 없이 열린다",
    ).toBe(GUEST_AUTHOR_ID);
    expect(grantedRoles[0], "게스트로는 쓰기가 열리면 안 된다").not.toBeOneOf([...WRITE_AUTHOR_IDS]);
  });
});
