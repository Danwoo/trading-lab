// #388 — 가입 API(`app/api/common/signup/route.ts`)의 요청 경계 검증. 클라이언트 폼을 거치지
// 않고 API 를 직접 호출하면 막히지 않던 입력들이다. #266 이 name·dept 를 막았고, 이 파일은
// 남은 필드(email 길이 · password 길이·타입 · 본문 파싱)를 같은 자리에서 막는다.
//
// **불변식**: 요청 경계를 통과하지 못하는 입력은 **DB·better-auth 에 닿기 전에** 400 이다.
// 경계에서 못 막으면 그 뒤 층이 던지고(P2000 · PASSWORD_TOO_LONG · SyntaxError), 그것들은
// 라우트의 catch 가 전부 `500 Internal Server Error!` 로 뭉갠다 — 클라이언트가 보낸 값이
// 서버 오류로 보고되고, 무엇이 잘못됐는지도 알 수 없다.
//
// **검증 경계** — prisma·better-auth 는 mock 이라 "DB 가 실제로 P2000 을 던진다"를 여기서
// 보지는 않는다. 보는 것은 **경계가 그 층에 닿기 전에 접는가**다: mock 이 한 번도 안 불렸으면
// 어떤 DB·인증 구현을 붙여도 그 층의 오류가 날 수 없다. 컬럼 길이(email VARCHAR(100),
// name 100, dept 50 — prisma/schema.prisma)와 스키마 상한이 어긋나지 않는지는 아래
// 마지막 describe 가 schema.prisma 를 직접 읽어 대조한다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

vi.mock("@/env", () => ({ env: { NODE_ENV: "development", EDITION: "saas" } }));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

const signUpEmail = vi.fn(async ({ body }: any) => ({ user: { id: "new-user", email: body.email } }));
vi.mock("@/lib/auth/auth", () => ({ auth: { api: { signUpEmail } } }));

const prismaCalls: string[] = [];
function record<T>(label: string, value: T) {
  prismaCalls.push(label);
  return Promise.resolve(value);
}

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    user: {
      // 첫 조회는 "중복 없음", 생성 뒤 조회는 "만들어짐" — 정상 경로가 끝까지 흐르게 한다.
      findUnique: vi.fn((args: any) => record("user.findUnique", args?.where?.id ? { id: "new-user" } : null)),
      update: vi.fn(() => record("user.update", {})),
    },
    workspaceDomain: { findFirst: vi.fn(() => record("workspaceDomain.findFirst", null)) },
    authorMember: { create: vi.fn(() => record("authorMember.create", {})) },
    $transaction: vi.fn(async (fn: any) =>
      fn({
        user: { update: vi.fn(() => record("tx.user.update", {})) },
        authorMember: { create: vi.fn(() => record("tx.authorMember.create", {})) },
      }),
    ),
  },
}));

// #343 이 가입에 세운 이메일 인증 관문. 이 파일이 보는 것은 **요청 경계 검증**이라
// 인증은 통과한 것으로 두고, 그 관문 자체는 `343-signup-requires-verification.test.ts` 가 본다.
vi.mock("@/lib/auth/signupVerificationGrant", () => ({
  consumeSignupVerificationGrant: vi.fn(async (_email: string, token: unknown) => token === VERIFICATION_TOKEN),
}));

vi.mock("@/lib/auth/authUtils", () => ({
  normalizeEmail: (e: string) => e.trim().toLowerCase(),
  ensurePersonalWorkspace: vi.fn(async () => 1),
  syncDefaultWorkspaceMembership: vi.fn(async () => undefined),
  resolveOemSharedWorkspace: vi.fn(async () => ({ id: 1 })),
  deleteHalfCreatedUser: vi.fn(async () => undefined),
}));

/** 본문을 문자열 그대로 실어 보낸다 — 깨진 JSON·null 본문을 재현하려면 직렬화를 우리가 쥐어야 한다. */
function postWithRawBody(body: string): NextRequest {
  return new NextRequest("http://localhost/api/common/signup", {
    method: "POST",
    body,
    headers: { "content-type": "application/json" },
  });
}

async function callPost(body: string) {
  const mod: any = await import("@/app/api/common/signup/route");
  return (await mod.POST(postWithRawBody(body))) as Response;
}

const VERIFICATION_TOKEN = "verified-by-otp";
const VALID = {
  email: "user@example.com",
  password: "abcd1234!",
  name: "홍길동",
  dept: "개발팀",
  verificationToken: VERIFICATION_TOKEN,
};

// regex(`[^\s@]+@[^\s@]+\.[^\s@]+`)는 통과하면서 100자를 넘는 이메일 — 정규식만으로는 안 막힌다.
const LONG_EMAIL = `${"a".repeat(95)}@example.com`;

// `status` 는 이 라우트의 기존 규약을 그대로 따른다: 새로 붙인 경계 검증은 400(#266 이 세운
// 방식), 원래 있던 email 형식·password 최소길이 가드는 `{result:false, name}` + 200 이다
// (가입 폼이 그 두 필드에 한해 name 으로 안내 문구를 고른다 — axios 는 400 에서 throw 라
// 200 을 400 으로 바꾸면 그 안내가 사라진다). 어느 쪽이든 **거절**이라는 점은 같고,
// 아래 단정이 실제로 보는 것은 "DB·better-auth 에 닿기 전에 접혔는가"다.
type Case = { label: string; body: string; status: number };

const REJECTED: Case[] = [
  {
    label: "email 101자 (정규식은 통과, VARCHAR(100) 초과)",
    body: JSON.stringify({ ...VALID, email: LONG_EMAIL }),
    status: 400,
  },
  { label: "깨진 JSON", body: '{"email":', status: 400 },
  { label: "본문이 JSON null", body: "null", status: 400 },
  { label: "본문이 JSON 배열", body: "[]", status: 400 },
  {
    label: "password 73자 (better-auth 상한 72 초과)",
    body: JSON.stringify({ ...VALID, password: "a1!".repeat(30) }),
    status: 400,
  },
  { label: "password 가 문자열이 아님(숫자)", body: JSON.stringify({ ...VALID, password: 12345678 }), status: 200 },
  { label: "name 101자", body: JSON.stringify({ ...VALID, name: "가".repeat(101) }), status: 400 },
  { label: "dept 51자", body: JSON.stringify({ ...VALID, dept: "가".repeat(51) }), status: 400 },
];

beforeEach(() => {
  prismaCalls.length = 0;
  signUpEmail.mockClear();
});

describe(`#388 가입 요청 경계 — 거절돼야 하는 입력 ${REJECTED.length}종`, () => {
  it.each(REJECTED)("$label 은 거절되고 DB·better-auth 에 닿지 않는다 (status $status)", async ({ body, status }) => {
    const res = await callPost(body);

    expect(res.status).toBe(status);
    expect(await res.json()).toMatchObject({ result: false });
    // 여기까지 왔으면 그 뒤 층이 던질 일이 없다 — P2000·PASSWORD_TOO_LONG 이 500 으로 새던 경로.
    expect(prismaCalls, `prisma 에 닿았다: ${prismaCalls.join(", ")}`).toEqual([]);
    expect(signUpEmail).not.toHaveBeenCalled();
  });

  it("목록이 줄지 않았다 (fail-closed)", () => {
    expect(REJECTED.length).toBe(8);
  });
});

describe("#388 정상 가입은 그대로 통과한다 (거절이 정상 경로를 갉아먹지 않는다)", () => {
  it("유효한 본문은 200 이고 better-auth 까지 간다", async () => {
    const res = await callPost(JSON.stringify(VALID));

    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ result: true });
    expect(signUpEmail).toHaveBeenCalledTimes(1);
  });

  it("dept 가 없어도 통과한다 (선택 필드)", async () => {
    const { dept: _dept, ...withoutDept } = VALID;
    const res = await callPost(JSON.stringify(withoutDept));
    expect(res.status).toBe(200);
  });

  it("경계값은 통과한다 — email 100자 · password 72자 · name 100자 · dept 50자", async () => {
    const res = await callPost(
      JSON.stringify({
        email: `${"a".repeat(88)}@example.com`, // 100자
        password: "a1!".repeat(24), // 72자
        name: "가".repeat(100),
        dept: "가".repeat(50),
        verificationToken: VERIFICATION_TOKEN,
      }),
    );
    expect(res.status).toBe(200);
  });
});

// 가입 흐름은 라우트 하나가 아니다: OTP 발송(email) → OTP 검증(email/verify) → 가입(signup).
// #388 이 signup 에서 잡은 "본문 파싱·타입 가드 부재 → 500" 은 같은 흐름의 verify 에도 있었다
// (발송 라우트는 이미 `.catch(() => null)` + 타입 가드로 막고 있었다 — 셋 중 하나만 빠져 있었다).
describe("#388 같은 클래스 — OTP 검증 라우트(가입 흐름)도 본문·타입을 접는다", () => {
  async function callVerify(body: string) {
    const mod: any = await import("@/app/api/common/email/verify/route");
    return (await mod.POST(
      new NextRequest("http://localhost/api/common/email/verify", {
        method: "POST",
        body,
        headers: { "content-type": "application/json" },
      }),
    )) as Response;
  }

  it.each([
    ["깨진 JSON", '{"email":', 400],
    ["본문이 JSON null", "null", 400],
    ["본문이 JSON 배열", "[]", 400],
    // otp 가 문자열이 아니면 crypto.createHash().update() 가 TypeError 를 던졌다 → 500.
    ["otp 가 문자열이 아님(숫자)", JSON.stringify({ email: "user@example.com", otp: 123456 }), 200],
  ])("%s 은 거절되고 DB 에 닿지 않는다 (status %i)", async (_label, body, status) => {
    const res = await callVerify(body as string);

    expect(res.status).toBe(status);
    expect(await res.json()).toMatchObject({ result: false });
    expect(prismaCalls, `prisma 에 닿았다: ${prismaCalls.join(", ")}`).toEqual([]);
  });
});

describe("#388 스키마 상한과 DB 컬럼 길이가 어긋나지 않는다", () => {
  const schemaPrisma = fs.readFileSync(path.join(FRONTEND_ROOT, "prisma/schema.prisma"), "utf-8");

  /** `model User { ... }` 블록 안에서 해당 컬럼의 `@db.VarChar(n)` 을 읽는다. */
  function varcharLength(field: string): number {
    const model = schemaPrisma.match(/model User \{([\s\S]*?)\n\}/);
    expect(model, "schema.prisma 에서 model User 를 못 찾았다 (경로·이름이 바뀌었나)").toBeTruthy();
    const line = model![1].split("\n").find((l) => new RegExp(`^\\s*${field}\\s`).test(l));
    expect(line, `model User 에 ${field} 컬럼이 없다`).toBeTruthy();
    const varchar = line!.match(/@db\.VarChar\((\d+)\)/);
    expect(varchar, `${field} 에 @db.VarChar 가 없다`).toBeTruthy();
    return Number(varchar![1]);
  }

  it.each([
    ["email", 100],
    ["name", 100],
    ["dept", 50],
  ])("User.%s 는 VARCHAR(%i) — 요청 경계 상한과 같다", (field, expected) => {
    expect(varcharLength(field)).toBe(expected);
  });
});
