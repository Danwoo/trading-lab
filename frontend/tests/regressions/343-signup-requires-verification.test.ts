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
import { createHash } from "node:crypto";
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
      // `authorMember.count` — 새 계정이라 기존 권한 행이 없다; `grantDefaultAuthor` 가 먼저 센다 (#355).
      fn({
        user: { update: vi.fn(async () => ({})) },
        authorMember: { count: vi.fn(async () => 0), create: vi.fn(async () => ({})) },
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

// ─────────────────────────────────────────────────────────────────────────────
// **다리** — OTP 검증 라우트가 내주는 증거를 가입이 실제로 받는가.
//
// 위 블록들은 증거를 함수로 직접 발급해 가입만 시험한다. 그래서 검증 라우트가 증거를 내주지
// 않게 되어도(예: 응답에서 `verificationToken` 이 빠져도) 전부 초록으로 남는다 — 그러면 서버는
// 여전히 안전하지만 **정상 가입이 통째로 막힌다.** 두 라우트를 이어서 부르는 그물이 있어야
// 그 고장이 드러난다.
describe("#343 OTP 검증 라우트 → 가입: 서버가 순서를 잇는다", () => {
  const OTP = "A1b2C3";
  const OTP_IDENTIFIER = `email-verification-otp-${EMAIL}`;

  /** 발송 라우트가 남기는 것과 같은 모양의 OTP 행 (`${sha256(otp)}:${시도횟수}`). */
  function seedOtpRow() {
    verificationRows.push({
      id: "otp-row",
      identifier: OTP_IDENTIFIER,
      value: `${createHash("sha256").update(OTP).digest("base64url")}:0`,
      expiresAt: new Date(Date.now() + 15 * 60 * 1000),
    });
  }

  async function callVerify(body: Record<string, unknown>): Promise<Response> {
    const mod: any = await import("@/app/api/common/email/verify/route");
    return mod.POST(
      new NextRequest("http://localhost/api/common/email/verify", {
        method: "POST",
        body: JSON.stringify(body),
        headers: { "content-type": "application/json" },
      }),
    );
  }

  it("맞힌 OTP → 증거를 받고, 그 증거로 가입이 통과한다", async () => {
    seedOtpRow();

    const verified = await callVerify({ email: EMAIL, otp: OTP });
    expect(verified.status).toBe(200);
    const { result, verificationToken } = (await verified.json()) as {
      result: boolean;
      verificationToken?: string;
    };
    expect(result).toBe(true);
    // 라우트가 증거를 안 내주면 여기서 멈춘다 — 정상 가입이 막히는 고장이다.
    expect(typeof verificationToken).toBe("string");
    expect(verificationToken).not.toBe("");

    const res = await callSignup({ ...BASE, verificationToken });
    expect(res.status).toBe(200);
    expect(signUpEmail).toHaveBeenCalledTimes(1);
  });

  it("증거는 **해시로만** 저장된다 — DB 를 읽어도 원문을 집어가지 못한다", async () => {
    seedOtpRow();
    const { verificationToken } = (await (await callVerify({ email: EMAIL, otp: OTP })).json()) as {
      verificationToken: string;
    };

    const grant = verificationRows.find((r) => r.identifier === emailVerifiedGrantIdentifier(EMAIL));
    expect(grant).toBeDefined();
    expect(grant!.value).not.toBe(verificationToken);
    expect(grant!.value).toBe(createHash("sha256").update(verificationToken).digest("base64url"));
  });

  it("틀린 OTP → 증거가 없고, 가입도 막힌다", async () => {
    seedOtpRow();

    const verified = await callVerify({ email: EMAIL, otp: "WRONG1" });
    expect(await verified.json()).toEqual({ result: false });
    expect(verificationRows.some((r) => r.identifier === emailVerifiedGrantIdentifier(EMAIL))).toBe(false);

    const res = await callSignup({ ...BASE, verificationToken: "anything" });
    expect(res.status).toBe(403);
    expect(signUpEmail).not.toHaveBeenCalled();
  });
});
