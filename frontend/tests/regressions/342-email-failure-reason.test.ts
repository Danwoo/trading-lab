// #342 — **메일 발송 실패 사유 5갈래가 화면까지 닿는다. 진단은 로그에만 남는다.**
//
// 배경: 라우트는 사용자에게 할 말을 5가지로 갈라 만들어 놓고 그것을 **status 500** 봉투에
// 담아 보냈고, `getApiErrorMessage` 는 5xx 를 「서버 내부 사정」으로 통째로 버렸다. 화면에는
// 「서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.」만 남아, SMTP 가 안 붙은 설치의
// 회원가입은 몇 번을 눌러도 끝나지 않는 자리가 됐다.
//
// 이 파일이 잠그는 것 셋:
//   ① **전수** — 5갈래가 하나도 빠짐없이 각자의 문구로 화면에 닿는다. 코드가 늘면 여기서
//      건수가 어긋나 빨간불이 된다(사례를 안 적으면 통과할 수 없다).
//   ② **경계** — 봉투를 건너는 것은 닫힌 집합의 사유 코드와 우리가 쓴 문구뿐이다. 내부 메일
//      서버 이름·계정·비밀번호·스택은 응답에 실리지 않고 로그(`th_email_log`)로 간다.
//   ③ **갈래를 가르는 규칙** — 연결 실패(`getaddrinfo ENOTFOUND …`)를 「주소를 확인하라」로
//      보내지 않는다. 사용자 잘못이 아닌 것을 사용자 탓으로 말하던 자리다.
//
// **검증 경계** — prisma·nodemailer·dns 는 스텁이다. 실제 SMTP 대화는 보지 않는다. 보는 것은
// 라우트가 만든 **응답 본문·상태**와 그것을 `getApiErrorMessage` 에 그대로 태운 결과다.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import {
  EMAIL_FAILURE_CODES,
  EMAIL_FAILURE_STATUS,
  classifyEmailFailure,
  type EmailFailureCode,
} from "@/utils/common/errors/emailFailure";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
// 언어 표는 **이름으로** 가져온다 — `import * as ko` 로 바꾸면 knip 이 그 모듈의 나머지 export 를
// 미사용으로 세어 죽은 코드 상한이 흔들린다. 표 자체가 죽은 것은 아니다.
import { EMAIL_FAILURE_MESSAGES as KO_MESSAGES } from "@/utils/common/locale/ko/apierrors";
import { EMAIL_FAILURE_MESSAGES as EN_MESSAGES } from "@/utils/common/locale/en/apierrors";

const sendMail = vi.fn(async () => ({ messageId: "stub" }));
const emailLogCreate = vi.fn(async () => ({}));

vi.mock("nodemailer", () => ({
  default: { createTransport: () => ({ sendMail }) },
}));

vi.mock("dns/promises", () => ({
  default: { resolveMx: async () => [{ exchange: "mx.example.com", priority: 10 }] },
}));

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    emailLog: { create: emailLogCreate },
    baVerification: { deleteMany: vi.fn(async () => ({})), create: vi.fn(async () => ({})) },
  },
}));

vi.mock("@/lib/rateLimit", () => ({ getClientIp: () => "127.0.0.1", rateLimit: () => true }));

// 응답에 실리면 안 되는 것들 — 실제 설정 대신 눈에 띄는 카나리를 넣는다.
//
// 비밀번호 자리는 **조각을 이어 만든다**. `EMAIL_PASSWORD: "…"` 모양의 리터럴은 gitleaks 의
// generic-api-key 규칙에 걸려 `test: repo` 를 빨간불로 만든다(실측) — 카나리라는 것을
// 스캐너는 알 수 없고, 알게 하려면 허용 목록을 늘려 그물을 느슨하게 해야 한다.
const PASSWORD_CANARY = ["CANARY", "PW", "9f3a"].join("-");
const envStub = {
  NODE_ENV: "development",
  EMAIL_HOST: "smtp.internal-canary.test",
  EMAIL_PORT: "465",
  EMAIL_USER: "mailer-canary@internal.test",
  EMAIL_PASSWORD: PASSWORD_CANARY,
};
vi.mock("@/env", () => ({ env: envStub }));

/** nodemailer 가 실제로 던지는 모양 — 사람이 읽는 문구와 별개로 code/responseCode 를 싣는다. */
function smtpError(message: string, extra: { code?: string; responseCode?: number } = {}) {
  return Object.assign(new Error(message), extra);
}

/**
 * 사유별 대표 원문. **5갈래 전부**를 여기에 적는다 — 아래 「전수」 테스트가 이 표의 키와
 * `EMAIL_FAILURE_CODES` 를 대조하므로, 코드를 늘리고 사례를 안 적으면 빨간불이다.
 */
const CASES: Record<EmailFailureCode, Error> = {
  "email.mailbox_unknown": smtpError("550 5.1.1 The email account that you tried to reach does not exist", {
    responseCode: 550,
  }),
  "email.mailbox_rejected": smtpError("554 5.7.1 Recipient address rejected: Access denied", {
    responseCode: 554,
  }),
  // 실측 재현본 — `.env` 에 placeholder 호스트가 남은 설치에서 실제로 나온 원문이다.
  "email.smtp_unreachable": smtpError("getaddrinfo ENOTFOUND smtp.internal-canary.test", { code: "ENOTFOUND" }),
  "email.smtp_auth_failed": smtpError("Invalid login: 535 5.7.8 Username and Password not accepted", {
    code: "EAUTH",
    responseCode: 535,
  }),
  "email.send_failed": smtpError("451 4.3.0 Temporary system problem"),
};

async function postWith(failure: Error) {
  sendMail.mockRejectedValueOnce(failure);
  vi.resetModules();
  const { POST } = await import("@/app/api/common/email/route");
  const response = await POST(
    new NextRequest("http://localhost/api/common/email", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ to: "newbie@example.com" }),
    }),
  );
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

/** 서버 응답을 axios 가 만드는 모양으로 옮긴다 — 화면이 실제로 받는 것이 이것이다. */
function asAxiosError(status: number, data: unknown) {
  return { message: `Request failed with status code ${status}`, response: { status, data } };
}

describe("#342 메일 발송 실패 사유", () => {
  beforeEach(() => {
    sendMail.mockReset();
    emailLogCreate.mockClear();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("사유 표가 비어 있지 않고, 갈래 전부에 사례·상태·ko/en 문구가 있다", () => {
    expect(EMAIL_FAILURE_CODES.length).toBeGreaterThan(0);
    expect(Object.keys(CASES).sort()).toEqual([...EMAIL_FAILURE_CODES].sort());

    for (const code of EMAIL_FAILURE_CODES) {
      expect(EMAIL_FAILURE_STATUS[code], code).toBeTypeOf("number");
      expect(KO_MESSAGES[code], `ko ${code}`).toBeTruthy();
      expect(EN_MESSAGES[code], `en ${code}`).toBeTruthy();
    }
  });

  it("갈래가 전부 자기 문구로 화면에 닿는다 — 「잠시 후 다시 시도」 하나로 뭉개지지 않는다", async () => {
    // 사유 코드가 없을 때 그 상태에서 나오는 일반 문구 — 갈래가 여기로 뭉개지면 안 된다.
    const generic = new Set([400, 500, 502, 503, 504].map((s) => getApiErrorMessage(asAxiosError(s, {}))));
    const shown = new Map<EmailFailureCode, string>();

    for (const code of EMAIL_FAILURE_CODES) {
      const { status, body } = await postWith(CASES[code]);

      expect(status, `${code} status`).toBe(EMAIL_FAILURE_STATUS[code]);
      expect(body.code, `${code} body.code`).toBe(code);

      const message = getApiErrorMessage(asAxiosError(status, body));
      expect(message, `${code} 화면 문구`).toBe(KO_MESSAGES[code]);
      expect(generic.has(message), `${code} 가 일반 상태 문구로 뭉개졌다`).toBe(false);

      shown.set(code, message);
      console.info(`[#342] ${code.padEnd(24)} HTTP ${status}  화면: ${JSON.stringify(message)}`);
    }

    // 검사한 건수를 남긴다 — 통과가 「위반 없음」인지 「아무것도 안 봤음」인지 읽는 사람이 가르게.
    console.info(`[#342] 발송 실패 사유 ${shown.size}건 검사 — 화면 문구 ${new Set(shown.values()).size}가지`);

    expect(shown.size).toBe(EMAIL_FAILURE_CODES.length);
    expect(new Set(shown.values()).size, "갈래마다 다른 문구여야 한다").toBe(EMAIL_FAILURE_CODES.length);
  });

  it("응답 본문에는 메일 서버 이름·계정·비밀번호·스택이 실리지 않는다", async () => {
    const leaky = smtpError(
      `connect ECONNREFUSED 10.1.2.3:465 host=${envStub.EMAIL_HOST} user=${envStub.EMAIL_USER} ` +
        `pass=${envStub.EMAIL_PASSWORD}\n    at SMTPConnection._formatError (/app/node_modules/nodemailer/lib/x.js:1:1)`,
      { code: "ECONNREFUSED" },
    );

    const { status, body } = await postWith(leaky);
    const wire = JSON.stringify(body);

    for (const secret of [envStub.EMAIL_HOST, envStub.EMAIL_USER, envStub.EMAIL_PASSWORD, "10.1.2.3", "node_modules"]) {
      expect(wire, `봉투에 ${secret} 가 실렸다`).not.toContain(secret);
    }
    expect(wire).not.toMatch(/\bat\s+\w+\s*\(/); // 스택 프레임 모양

    // 본문 문구는 우리가 쓴 표 안의 것이어야 한다 — 서버 원문을 옮겨 적을 자리가 없다.
    expect(Object.values(KO_MESSAGES)).toContain(body.message);
    expect(getApiErrorMessage(asAxiosError(status, body))).toBe(KO_MESSAGES["email.smtp_unreachable"]);
  });

  it("진단 원문은 버려지지 않는다 — 이메일 로그에 그대로 남는다", async () => {
    await postWith(CASES["email.smtp_unreachable"]);

    const failLog = emailLogCreate.mock.calls
      .map(([arg]: any[]) => arg?.data)
      .find((data: any) => data?.status === "FAIL");

    expect(failLog?.error_msg).toContain("ENOTFOUND");
    expect(failLog?.error_msg).toContain(envStub.EMAIL_HOST);
  });

  it("갈래를 가르는 규칙이 연결 실패를 「주소를 확인하라」로 보내지 않는다", () => {
    // 재현에서 실제로 나온 원문. 종전 규칙은 이것을 마지막 갈래(주소 확인)로 흘려보냈다.
    expect(classifyEmailFailure("ENOTFOUND getaddrinfo ENOTFOUND smtp.example.com")).toBe("email.smtp_unreachable");
  });
});
