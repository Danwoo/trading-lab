/**
 * 가입 마법사 1단계가 받은 **서버 발급 인증 증거**를 2단계까지 나르는 sessionStorage 키 (#343).
 *
 * 상수로 두는 이유는 넣는 곳(1단계)과 꺼내는 곳(2단계)이 다른 파일이라서다 — 문자열이 갈리면
 * 2단계가 조용히 빈 값을 보내고, 서버는 인증 없음으로 거절한다.
 */
export const SIGNUP_VERIFICATION_TOKEN_KEY = "signupVerificationToken";
