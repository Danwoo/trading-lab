// utils/common/errors/emailFailure.ts
//
// 메일 발송 실패를 **사유 코드**로 옮긴다 (#342). 봉투를 건너는 것은 이 닫힌 집합의 코드뿐이고
// SMTP 원문은 여기서 버려진다 — 원문에는 내부 메일 서버 이름이 그대로 실린다(실측:
// `frontend.th_email_log.error_msg` = `getaddrinfo ENOTFOUND smtp.example.com`). 화면 문구는
// 받는 쪽이 자기 언어 표(`locale/*/apierrors.ts`)에서 고른다.
//
// 서버(`app/api/common/email/route.ts`)와 클라이언트(`errors/apierrors.ts`)가 함께 쓰므로
// 순수 모듈이다 — env·prisma·nodemailer 를 물지 않는다.

export const EMAIL_FAILURE_CODES = [
  "email.mailbox_unknown",
  "email.mailbox_rejected",
  "email.smtp_unreachable",
  "email.smtp_auth_failed",
  "email.send_failed",
] as const;

export type EmailFailureCode = (typeof EMAIL_FAILURE_CODES)[number];

/**
 * 사유별 HTTP 상태.
 *
 * 주소가 틀린 것은 **사용자가 고칠 수 있는 실패**라 4xx 로, 메일 서버 사정은 5xx 로 나간다.
 * 어느 쪽이든 화면 문구는 상태가 아니라 `code` 로 건너가므로 `apierrors.ts` 의 5xx 차단
 * (서버가 쓴 문장을 화면에 싣지 않는다) 은 그대로 선다.
 */
export const EMAIL_FAILURE_STATUS: Record<EmailFailureCode, number> = {
  "email.mailbox_unknown": 400,
  "email.mailbox_rejected": 400,
  "email.smtp_unreachable": 503,
  "email.smtp_auth_failed": 503,
  "email.send_failed": 502,
};

/**
 * 위에서 아래로 첫 매칭이 이긴다 — 순서가 계약이다.
 *
 * 연결 갈래에 DNS·소켓 코드(`ENOTFOUND`·`EAI_AGAIN`·`ESOCKET`…)를 함께 둔다: `.env` 에
 * placeholder 호스트가 남은 설치에서 실제로 나오는 원문이 `getaddrinfo ENOTFOUND …` 인데,
 * 종전 규칙(`/connect|timeout|ECONNREFUSED|ETIMEDOUT/`)은 이것을 어디에도 못 걸어 마지막
 * 갈래(「주소를 확인하라」)로 보냈다 — **사용자 잘못이 아닌 것을 사용자 탓으로 말했다**(#342 재현).
 */
const PATTERNS: ReadonlyArray<readonly [RegExp, EmailFailureCode]> = [
  [
    /user.*unavailable|account.*unavailable|no such user|user.*not.*exist|does not exist|unknown user|invalid.*mailbox/i,
    "email.mailbox_unknown",
  ],
  [/rejected|denied|not allowed/i, "email.mailbox_rejected"],
  [
    /connect|timeout|ECONNREFUSED|ETIMEDOUT|ECONNRESET|ENOTFOUND|EAI_AGAIN|EHOSTUNREACH|ENETUNREACH|ESOCKET|ECONNECTION|getaddrinfo/i,
    "email.smtp_unreachable",
  ],
  [/authentication|credentials|invalid login|EAUTH|\bauth\b|\b53[45]\b/i, "email.smtp_auth_failed"],
];

/** SMTP 실패 원문(+ nodemailer 코드) → 사유 코드. 어디에도 안 걸리면 일반 실패. */
export function classifyEmailFailure(raw: string): EmailFailureCode {
  for (const [pattern, code] of PATTERNS) {
    if (pattern.test(raw)) return code;
  }
  return "email.send_failed";
}

/**
 * 진단용 원문 — nodemailer 는 사람이 읽는 문구와 별개로 `code`(`EAUTH`·`ESOCKET`)·`responseCode`
 * (535·550) 를 실어 준다. 갈래를 가르는 데 셋 다 쓴다. **로그에만 남는 값이다.**
 */
export function describeSmtpError(error: unknown): string {
  const parts: string[] = [];
  const candidate = error as { code?: unknown; responseCode?: unknown } | null;
  if (candidate?.code != null) parts.push(String(candidate.code));
  if (candidate?.responseCode != null) parts.push(String(candidate.responseCode));
  parts.push(error instanceof Error ? error.message : String(error));
  return parts.join(" ");
}

export function isEmailFailureCode(value: unknown): value is EmailFailureCode {
  return typeof value === "string" && (EMAIL_FAILURE_CODES as readonly string[]).includes(value);
}
