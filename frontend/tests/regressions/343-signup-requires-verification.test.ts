// #343 — **이메일 인증 없이 계정이 만들어지지 않는다.**
//
// 종전에는 마법사 1단계(OTP)가 리액트 상태일 뿐이라, 화면을 거치지 않고 가입 API 를 직접
// 부르면 인증을 한 번도 통과하지 않은 계정이 `emailVerified = true` 로 만들어졌다. 남의
// 주소로도 됐다 — 그 요청은 주소의 소유를 한 번도 확인하지 않았다.
//
// **불변식**: `POST /api/common/signup` 은 「그 주소의 OTP 를 맞혔다」는 **서버 증거**를
// 소비하지 못하면 better-auth 에 닿기 전에 403 으로 접는다.
//
// **검증 경계** — `prisma` 는 mock 이지만 `ba_verification` 은 실제 테이블처럼 동작하는
// 인메모리 저장소로 두었다. 그래서 증거의 해싱·만료·단일 사용 규칙
// (`lib/auth/signupVerificationGrant.ts`)은 **진짜 코드가 돈다**. mock 인 것은 DB 엔진뿐이다.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { emailVerifiedGrantIdentifier } from "@/lib/auth/verificationIdentifier";

vi.mock("@/env", () => ({ env: { NODE_ENV: "development", EDITION: "saas" } }));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

const signUpEmail = vi.fn(async ({ body }: any) => ({ user: { id: "new-user", email: body.email } }));
vi.mock("@/lib/auth/auth", () => ({ auth: { api: { signUpEmail } } }));

/** `ba_verification` 을 대신하는 인메모리 저장소 — 증거 로직은 진짜 코드가 이것을 상대로 돈다. */
type Row = { id: string; identifier: string; value: string; expiresAt: Date };
const verificationRows: Row[] = [];

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(async (args: any) => (args?.where?.id ? { id: "new-user" } : null)),
      update: vi.fn(async () => ({})),
    },
    baVerification: {
      findFirst: vi.fn(async (args: any) => verificationRows.find((r) => r.identifier === args.where.identifier) ?? null),
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
    },
    workspaceDomain: { findFirst: vi.fn(async () => null) },
    authorMember: { create: vi.fn(async () => ({})) },
    $transaction: vi.fn(async (fn: any) =>
      fn({ user: { update: vi.fn(async () => ({})) }, authorMember: { create: vi.fn(async () => ({})) } }),
    ),
  },
}));

vi.mock("@/lib/auth/authUtils", () => ({
  normalizeEmail: (e: string) => e.trim().toLowerCase(),
  ensurePersonalWorkspace: vi.fn(async () => 1),
  syncDefaultWorkspaceMembership: vi.fn(async () => undefined),
  resolveOemSharedWorkspace: vi.fn(async () => ({ id: 1 })),
  deleteHalfCreatedUser: vi.fn(async () => undefined),
}));

const EMAIL = "newcomer@example.com";
const BASE = { email: EMAIL, password: "abcd1234!", name: "홍길동", dept: "개발팀" };

async function callSignup(body: Record<string, unknown>): Promise<Response> {
  const mod: any = await import("@/app/api/common/signup/route");
  return mod.POST(
    new NextRequest("http://localhost/api/common/signup", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }),
  );
}

/** OTP 검증 라우트가 하는 일과 같다 — 증거를 발급하고 원문 토큰을 돌려준다. */
async function issueGrant(email = EMAIL): Promise<string> {
  const { issueSignupVerificationGrant } = await import("@/lib/auth/signupVerificationGrant");
  return issueSignupVerificationGrant(email);
}

beforeEach(() => {
  verificationRows.length = 0;
  signUpEmail.mockClear();
});

// 인증 증거로 인정되지 **않는** 것들. 목록이 줄면 아래 마지막 단정이 실패한다.
const REJECTED: ReadonlyArray<{ label: string; build: () => Promise<Record<string, unknown>> }> = [
  {
    label: "verificationToken 필드가 아예 없다 (이슈가 재현한 그 요청)",
    build: async () => ({ ...BASE }),
  },
  { label: "verificationToken 이 빈 문자열", build: async () => ({ ...BASE, verificationToken: "" }) },
  { label: "verificationToken 이 문자열이 아니다 (숫자)", build: async () => ({ ...BASE, verificationToken: 12345 }) },
  { label: "verificationToken 이 true (타입 우회 시도)", build: async () => ({ ...BASE, verificationToken: true }) },
  {
    label: "발급받지 않은 임의의 토큰",
    build: async () => {
      await issueGrant();
      return { ...BASE, verificationToken: "not-the-real-token" };
    },
  },
  {
    label: "다른 주소로 발급받은 토큰 (남의 주소 선점 시도)",
    build: async () => ({ ...BASE, verificationToken: await issueGrant("someone-else@example.com") }),
  },
  {
    label: "만료된 증거",
    build: async () => {
      const token = await issueGrant();
      const row = verificationRows.find((r) => r.identifier === emailVerifiedGrantIdentifier(EMAIL))!;
      row.expiresAt = new Date(Date.now() - 1000);
      return { ...BASE, verificationToken: token };
    },
  },
  {
    label: "이미 소비된 증거 (한 번 쓴 토큰 재사용)",
    build: async () => {
      const token = await issueGrant();
      const { consumeSignupVerificationGrant } = await import("@/lib/auth/signupVerificationGrant");
      // 소비가 실제로 일어났음을 먼저 확인한다 — 안 그러면 이 케이스가 "소비 안 된 토큰"을
      // 시험하면서 조용히 통과할 수 있다.
      expect(await consumeSignupVerificationGrant(EMAIL, token)).toBe(true);
      return { ...BASE, verificationToken: token };
    },
  },
];

describe(`#343 인증 증거 없이는 계정이 만들어지지 않는다 — 거절 ${REJECTED.length}종`, () => {
  it.each(REJECTED)("$label → 403, better-auth 에 닿지 않는다", async ({ build }) => {
    const res = await callSignup(await build());

    expect(res.status).toBe(403);
    expect(await res.json()).toMatchObject({ result: false, name: "verification" });
    expect(signUpEmail).not.toHaveBeenCalled();
  });

  it("목록이 줄지 않았다 (fail-closed)", () => {
    expect(REJECTED.length).toBe(8);
  });
});

describe("#343 인증을 통과한 가입은 그대로 만들어진다", () => {
  it("발급받은 토큰이면 200 이고 better-auth 까지 간다", async () => {
    const res = await callSignup({ ...BASE, verificationToken: await issueGrant() });

    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ result: true });
    expect(signUpEmail).toHaveBeenCalledTimes(1);
  });

  it("성공한 가입은 증거를 소비한다 — 같은 토큰이 두 번째 계정을 만들지 못한다", async () => {
    const token = await issueGrant();
    expect(verificationRows).toHaveLength(1);

    const first = await callSignup({ ...BASE, verificationToken: token });
    expect(first.status).toBe(200);
    expect(verificationRows).toHaveLength(0);

    signUpEmail.mockClear();
    const second = await callSignup({ ...BASE, email: "second@example.com", verificationToken: token });
    expect(second.status).toBe(403);
    expect(signUpEmail).not.toHaveBeenCalled();
  });
});
