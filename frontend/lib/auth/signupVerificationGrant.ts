import crypto from "crypto";
import { prisma } from "@/lib/prisma/client";
import { emailVerifiedGrantIdentifier } from "@/lib/auth/verificationIdentifier";

/**
 * 「이 주소의 OTP 를 실제로 맞혔다」는 사실을 **서버에** 남기고, 가입이 그것을 소비하게 한다.
 *
 * 종전에는 이 사실이 브라우저의 리액트 상태·sessionStorage 로만 남아, 가입 API 를 직접 부르면
 * 인증을 한 번도 통과하지 않고 계정이 만들어졌다(#343). 검사를 **계정을 만드는 자리**로 옮기지
 * 않으면 마법사를 손댈 때마다 같은 구멍이 다시 열린다.
 *
 * 저장소는 OTP 와 같은 `ba_verification` 이다(별도 테이블을 늘리지 않는다). 규칙 셋:
 * - `identifier` 는 이메일로 조립하고(`emailVerifiedGrantIdentifier`), `value` 에는 토큰의
 *   **해시**만 둔다 — DB 를 읽을 수 있는 사람이 그대로 가입 자격을 집어가지 못하게.
 * - 수명을 둔다. 인증과 가입 사이가 하루씩 벌어지면 그 사이 주소를 잃은 사람도 통과한다.
 * - **한 번만 쓴다.** 소비는 `deleteMany` 가 1건을 지웠을 때만 성공으로 친다 — 동시에 들어온
 *   두 요청 중 하나만 이긴다(읽고-쓰기 사이의 경합을 DB 가 가른다).
 */
export const SIGNUP_VERIFICATION_GRANT_TTL_MS = 30 * 60 * 1000;

function hashGrantToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("base64url");
}

/** OTP 검증에 성공했을 때 발급한다. 반환값(원문 토큰)은 호출자가 그 자리에서 사용자에게만 준다. */
export async function issueSignupVerificationGrant(email: string): Promise<string> {
  const token = crypto.randomBytes(32).toString("base64url");
  const identifier = emailVerifiedGrantIdentifier(email);
  const now = new Date();

  // 같은 주소의 이전 증거는 남기지 않는다 — 인증을 다시 했으면 새 것 하나만 유효하다.
  await prisma.baVerification.deleteMany({ where: { identifier } });
  await prisma.baVerification.create({
    data: {
      id: crypto.randomUUID(),
      identifier,
      value: hashGrantToken(token),
      expiresAt: new Date(now.getTime() + SIGNUP_VERIFICATION_GRANT_TTL_MS),
      createdAt: now,
      updatedAt: now,
    },
  });

  return token;
}

/**
 * 가입이 부른다. **성공하면 증거를 소비**하므로 계정을 만들기 직전에 한 번만 부른다.
 * 실패 사유(없음·만료·불일치)를 호출자에게 가르지 않는 이유는 어느 쪽이든 답이 하나이기
 * 때문이다 — 인증부터 다시 한다.
 */
export async function consumeSignupVerificationGrant(email: string, token: unknown): Promise<boolean> {
  if (typeof token !== "string" || !token) return false;

  const identifier = emailVerifiedGrantIdentifier(email);
  const record = await prisma.baVerification.findFirst({ where: { identifier } });
  if (!record) return false;

  if (record.expiresAt < new Date()) {
    await prisma.baVerification.deleteMany({ where: { id: record.id } });
    return false;
  }

  const expected = Buffer.from(record.value);
  const actual = Buffer.from(hashGrantToken(token));
  if (expected.length !== actual.length || !crypto.timingSafeEqual(expected, actual)) return false;

  const { count } = await prisma.baVerification.deleteMany({ where: { id: record.id } });
  return count === 1;
}
