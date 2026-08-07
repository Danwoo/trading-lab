import { describe, expect, it } from "vitest";

import { EMAIL_VERIFICATION_OTP_PREFIX, emailVerificationOtpIdentifier } from "@/lib/auth/verificationIdentifier";

// 이 조립 규칙은 세 경로가 공유하는 계약이다 — 발송(app/api/common/email/route.ts)이 쓰고,
// 검증(.../email/verify/route.ts)이 읽고, 탈퇴 삭제(deleteUserCascade, #414)가 지운다.
// 셋이 각자 문자열을 조립하던 시절에는 한 곳만 바꿔도 나머지가 조용히 어긋난다 — 특히 삭제는
// 0건 삭제로 성공하므로 어긋난 것이 드러나지 않는다.
describe("emailVerificationOtpIdentifier — OTP 저장 키의 단일 조립 규칙", () => {
  it("접두어 + 정규화된 이메일로 조립한다", () => {
    expect(emailVerificationOtpIdentifier("user@example.com")).toBe(`${EMAIL_VERIFICATION_OTP_PREFIX}user@example.com`);
  });

  it("대소문자·공백 변형이 전부 같은 키로 수렴한다 (발송·검증·삭제가 같은 행을 가리킨다)", () => {
    const keys = ["User@Example.com", "USER@EXAMPLE.COM", "  user@example.com  "].map(emailVerificationOtpIdentifier);
    expect(new Set(keys).size).toBe(1);
    expect(keys[0]).toBe("email-verification-otp-user@example.com");
  });

  it("이미 조립·정규화된 이메일을 다시 넣어도 결과가 같다(멱등) — 호출부가 이중 정규화해도 안전", () => {
    const once = emailVerificationOtpIdentifier("Dup@Example.com");
    expect(emailVerificationOtpIdentifier(once.slice(EMAIL_VERIFICATION_OTP_PREFIX.length))).toBe(once);
  });

  it("서로 다른 이메일은 서로 다른 키가 된다 — 접두어 확장으로 남의 행을 가리키지 않는다", () => {
    // `a@x.test` 의 키가 `a@x.test.evil.test` 의 키의 접두어가 되는 것은 사실이다. 삭제가
    // 완전일치가 아니라 접두어·LIKE 로 바뀌면 그 순간 남의 행까지 지운다 — 그 경계를 여기서
    // 문자열 수준으로 못 박고, 행 수준은 deleteUserCascade.dbtest.ts 가 잡는다.
    const mine = emailVerificationOtpIdentifier("a@x.test");
    const other = emailVerificationOtpIdentifier("a@x.test.evil.test");
    expect(mine).not.toBe(other);
    expect(other.startsWith(mine)).toBe(true);
  });
});
