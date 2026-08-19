// #231 — **인증 코드를 콘솔에 찍는 길은 개발에만 열린다.**
//
// 배경: 메일 서버 없이 클론 직후 가입까지 가려면 인증 코드를 어딘가로 내보내야 한다.
// `app/api/common/email` 은 `EMAIL_HOST` 가 비어 있고 개발일 때에 한해 메일 대신 서버
// 콘솔에 코드를 찍는다. 이 문이 운영에서 열리면 인증 코드가 로그로 새어 계정 탈취
// 경로가 된다 — 그래서 두 조건의 **AND** 라는 사실을 여기서 잠근다.
//
// **검증 경계** — prisma·nodemailer·dns 는 스텁이다. 보는 것은 (1) 콘솔에 코드가 찍혔는가
// (2) 메일 전송이 시도됐는가 둘뿐이고, 실제 SMTP 동작은 보지 않는다.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const sendMail = vi.fn(async () => ({ messageId: "stub" }));

vi.mock("nodemailer", () => ({
  default: { createTransport: () => ({ sendMail }) },
}));

vi.mock("dns/promises", () => ({
  default: { resolveMx: async () => [{ exchange: "mx.example.com", priority: 10 }] },
}));

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    emailLog: { create: vi.fn(async () => ({})) },
    baVerification: { deleteMany: vi.fn(async () => ({})), create: vi.fn(async () => ({})) },
  },
}));

vi.mock("@/lib/rateLimit", () => ({ getClientIp: () => "127.0.0.1", rateLimit: () => true }));

const envStub = { NODE_ENV: "development", EMAIL_HOST: "", EMAIL_PORT: "465", EMAIL_USER: "u", EMAIL_PASSWORD: "p" };
vi.mock("@/env", () => ({ env: envStub }));

function request() {
  return new NextRequest("http://localhost/api/common/email", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ to: "someone@example.com" }),
  });
}

async function post() {
  vi.resetModules();
  const { POST } = await import("@/app/api/common/email/route");
  return POST(request());
}

describe("#231 콘솔 인증 코드는 개발 전용", () => {
  let logged: string[];

  beforeEach(() => {
    logged = [];
    sendMail.mockClear();
    vi.spyOn(console, "info").mockImplementation((...args: unknown[]) => {
      logged.push(args.map(String).join(" "));
    });
  });

  it("개발 + EMAIL_HOST 비어 있음 → 코드를 콘솔에 찍고 메일은 보내지 않는다", async () => {
    envStub.NODE_ENV = "development";
    envStub.EMAIL_HOST = "";

    const res = await post();

    expect(res.status).toBe(200);
    expect(sendMail).not.toHaveBeenCalled();
    expect(logged.filter((l) => l.includes("인증 코드"))).toHaveLength(1);
  });

  it("운영이면 EMAIL_HOST 가 비어 있어도 콘솔로 새지 않는다", async () => {
    envStub.NODE_ENV = "production";
    envStub.EMAIL_HOST = "";

    await post();

    expect(logged.filter((l) => l.includes("인증 코드"))).toHaveLength(0);
    expect(sendMail).toHaveBeenCalledTimes(1);
  });

  it("개발이어도 EMAIL_HOST 가 있으면 메일로 보낸다", async () => {
    envStub.NODE_ENV = "development";
    envStub.EMAIL_HOST = "smtp.real.test";

    await post();

    expect(logged.filter((l) => l.includes("인증 코드"))).toHaveLength(0);
    expect(sendMail).toHaveBeenCalledTimes(1);
  });
});
