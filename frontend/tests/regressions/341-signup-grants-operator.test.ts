// #341 — 가입이 배정하는 역할. 리드 결정 2026-08-23: **가입자는 자기 워크스페이스의 operator 다.**
//
// **불변식**: 정상 가입 한 건이 끝나면 `tn_author_member` 에 들어간 `author_id` 는 쓰기가 열리는
// 역할(`WRITE_AUTHOR_IDS`)이다. 게스트(`GUEST_AUTHOR_ID`)를 배정하면 그 계정은 실험대·시세·
// 관심종목의 저장·실행이 **전부 403** 이 된다 — 이 이슈의 원래 증상이다.
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
    workspaceDomain: { findFirst: vi.fn(async () => null) },
    authorMember: { create: vi.fn(async () => ({})) },
    $transaction: vi.fn(async (fn: any) =>
      fn({
        user: { update: vi.fn(async () => ({})) },
        authorMember: {
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
  ensurePersonalWorkspace: vi.fn(async () => 1),
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
  });
});
