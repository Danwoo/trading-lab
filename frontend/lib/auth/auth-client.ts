import { createAuthClient } from "better-auth/react";
import { jwtClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [jwtClient()],
});

// `signUp` 은 내보내지 않는다 — Better Auth 의 가입 엔드포인트는 이 제품에서 막혀 있다(#343).
// 내보내 두면 그것을 부르는 화면이 404 를 받고서야 이유를 찾게 된다. 가입은 `/api/common/signup`
// 한 문뿐이고, 그 앞에 이메일 인증이 서 있다.
export const { signIn, signOut, useSession, getSession } = authClient;
