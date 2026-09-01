/**
 * 가입 마법사 1단계가 받은 **서버 발급 인증 증거**를 2단계까지 나르는 sessionStorage 키 (#343).
 *
 * 상수로 두는 이유는 넣는 곳(1단계)과 꺼내는 곳(2단계)이 다른 파일이라서다 — 문자열이 갈리면
 * 2단계가 조용히 빈 값을 보내고, 서버는 인증 없음으로 거절한다.
 */
export const SIGNUP_VERIFICATION_TOKEN_KEY = "signupVerificationToken";

/**
 * 인증 코드가 **실제로 어디로 갔는가**. 서버(`app/api/common/email`)가 SMTP 설정을 보고
 * 정해 응답에 싣고, 가입 화면은 그 값을 읽어 말한다 (#424).
 *
 * 화면이 스스로 추측할 수 없는 값이라 응답에 싣는다 — `EMAIL_HOST` 는 서버만 안다.
 * `console` 은 개발 기본값(SMTP 미설정)에서만 나오고, 운영에서는 나오지 않는다.
 */
export type OtpDelivery = "email" | "console";
