// #424 ① — **인증 코드가 어디로 갔는지를 서버가 응답에 실어 보낸다.**
//
// 배경: `EMAIL_HOST` 가 비면(`.env.example` 의 기본값) 코드는 메일이 아니라 **서버 콘솔**에만
// 찍힌다. 그런데 응답은 두 경우에 똑같아서, 화면은 「메일을 보냈다」밖에 말할 수 없었다 —
// 처음 설치해 혼자 쓰는 사람이 정확히 이 모드로 가입하고 오지 않는 메일을 기다린다.
//
// 판정은 이미 라우트가 갖고 있다(`isConsoleOtpMode`). 여기서 잠그는 것은 그 판정이 **응답을
// 건너 화면까지 간다**는 사실이고, 동시에 그 문이 **운영에서는 열리지 않는다**는 #231 의
// 불변식이 이 변경으로 흔들리지 않았다는 것이다.
//
// **검증 경계** — prisma·nodemailer·dns 는 스텁이다. 보는 것은 라우트가 만든 응답 본문과
// 메일 전송 시도 여부뿐이고, 실제 SMTP 대화는 보지 않는다.

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

/** 이 표가 검사 단위다. 비면 아래 「검사 건수」 블록이 실패한다. */
const CASES = [
  {
    name: "개발 + EMAIL_HOST 비어 있음 → 콘솔",
    env: { NODE_ENV: "development", EMAIL_HOST: "" },
    delivery: "console",
    mailSent: false,
  },
  {
    name: "개발 + EMAIL_HOST 있음 → 메일",
    env: { NODE_ENV: "development", EMAIL_HOST: "smtp.real.test" },
    delivery: "email",
    mailSent: true,
  },
  {
    name: "운영 + EMAIL_HOST 비어 있음 → 메일 (콘솔 문은 운영에 없다)",
    env: { NODE_ENV: "production", EMAIL_HOST: "" },
    delivery: "email",
    mailSent: true,
  },
] as const;

const checked = new Set<string>();

async function post() {
  vi.resetModules();
  const { POST } = await import("@/app/api/common/email/route");
  return POST(
    new NextRequest("http://localhost/api/common/email", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ to: "someone@example.com" }),
    }),
  );
}

describe("#424 ① 발송 경로가 응답에 실린다", () => {
  beforeEach(() => {
    sendMail.mockClear();
    vi.spyOn(console, "info").mockImplementation(() => {});
  });

  it.each(CASES)("$name", async ({ name, env, delivery, mailSent }) => {
    envStub.NODE_ENV = env.NODE_ENV;
    envStub.EMAIL_HOST = env.EMAIL_HOST;

    const res = await post();
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.delivery).toBe(delivery);
    expect(sendMail).toHaveBeenCalledTimes(mailSent ? 1 : 0);

    checked.add(name);
  });

  it(`검사 건수 — ${CASES.length}가지 조합`, () => {
    expect(CASES.length).toBeGreaterThanOrEqual(3);
    expect([...checked].sort()).toEqual(CASES.map((c) => c.name).sort());
  });
});
