import { normalizeEmail } from "@/lib/auth/normalizeEmail";

/**
 * 가입 인증 OTP 가 `ba_verification.identifier` 에 쓰는 키 — **쓰는 곳·읽는 곳·지우는 곳이 같은 규칙**.
 *
 * 이 테이블에 행을 넣는 경로는 둘이고 모양이 다르다:
 * - **이 앱의 가입 OTP** (`app/api/common/email/route.ts`) — Better Auth 를 거치지 않고 Prisma 로
 *   직접 쓴다. 그래서 `identifier` 가 평문이고 **여기에만 이메일이 들어간다**.
 * - **Better Auth 자신** — 비밀번호 재설정(`reset-password:<token>`)뿐이고(1.6.11 기준 이 설정에서
 *   활성화된 유일한 verification 발급 경로), `auth.ts` 의 `verification.storeIdentifier: "hashed"`
 *   가 그 키를 SHA-256(base64url)으로 바꿔 저장한다 — 이메일도 토큰 원문도 남지 않는다.
 *   대신 그 행의 `value` 가 `tn_user.id` 원문이다.
 *
 * 키를 문자열 리터럴로 흩뿌리면 탈퇴 삭제(`deleteUserCascade`)가 지우는 키와 발송 라우트가 쓰는
 * 키가 갈라져 **조용히 아무것도 안 지운다** — 지우는 쪽은 0건 삭제로 성공하므로 신호가 없다.
 * 그래서 조립을 이 함수 하나로 모은다.
 *
 * `normalizeEmail` 을 여기서 통과시키는 이유는 호출부 셋(발송·검증·삭제)의 입력 출처가 다르기
 * 때문이다 — 앞의 둘은 요청 본문, 삭제는 `tn_user.email` 이다. 한 곳에서 정규화하면 세 경로가
 * 같은 키를 만든다 (이미 정규화된 값을 다시 넣어도 결과가 같다).
 *
 * `normalizeEmail.ts` 와 같은 이유로 prisma·env 를 물지 않는 순수 모듈로 둔다 — 이 조립 규칙만
 * `npm test`(node 환경)로 가볍게 고정하기 위해서다.
 */
export const EMAIL_VERIFICATION_OTP_PREFIX = "email-verification-otp-";

export function emailVerificationOtpIdentifier(email: string): string {
  return `${EMAIL_VERIFICATION_OTP_PREFIX}${normalizeEmail(email)}`;
}
