/**
 * 계정 식별자로서의 이메일 정규화 — **저장도 조회도 이 함수를 통과한 값만 쓴다.**
 *
 * Better Auth 는 사용자를 만들 때도 찾을 때도 `email.toLowerCase()` 로 맞춘다
 * (1.6.11 `/sign-up/email` · `internalAdapter.findUserByEmail`). 우리 조회가 입력 원문을
 * 그대로 쓰면 대문자로 가입한 사용자를 저장 직후부터 못 찾는다 (#250).
 *
 * 앞뒤 공백은 주소의 일부가 아니라 입력 사고라 함께 떨어낸다 — 이메일 검증 정규식과
 * Better Auth 의 `z.email()` 이 공백 있는 주소를 거부하므로 정규화가 검증보다 먼저다.
 *
 * 라우트마다 각자 `.toLowerCase()` 를 뿌리지 말고 요청 경계에서 이 함수 **한 번만** 통과시킨다 —
 * 흩어지면 이 함수를 고쳐도 빠뜨린 라우트만 옛 규칙에 남는다.
 *
 * 이 파일은 의도적으로 다른 모듈을 import 하지 않는다 — `@/lib/auth/authUtils` 는 prisma
 * 클라이언트를 top-level 에서 물어오고, prisma 클라이언트는 `@/env`(런타임 환경변수 스키마
 * 검증)를 물어온다. 이 함수를 authUtils 안에 두면 순수 로직 하나를 테스트하려 해도 vitest 가
 * DATABASE_URL 등 실 환경변수를 요구하며 죽는다(env-cmd 로 감싸지 않는 `vitest run` 기준
 * 실측) — 그래서 별도 파일로 뽑아 이 함수만 node 환경에서 가볍게 테스트한다.
 */
export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}
