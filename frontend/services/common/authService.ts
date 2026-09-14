import { apiCall } from "@/utils/common/api/client";
import type { OtpDelivery } from "@/constants/signup";

const EMAIL_URL = "/api/common/email";
const SIGNUP_URL = "/api/common/signup";

export const sendEmail = async (to: string) => {
  // `delivery` 는 코드가 실제로 간 곳이다 — 화면이 이것 없이 「메일을 보냈다」고 말하던 것이 #424.
  return apiCall<{ message: string; delivery: OtpDelivery }>(EMAIL_URL, {
    method: "POST",
    data: { to },
  });
};

export const verifySignupOTP = async (email: string, otp: string) => {
  // `verificationToken` 은 인증에 성공했다는 **서버 발급 증거**다 — 가입 요청이 이것을 되돌려
  // 줘야 계정이 만들어진다(#343). 클라이언트 상태로만 「인증됨」을 들고 있던 시절의 우회를 막는다.
  return apiCall<{ result: boolean; verificationToken?: string }>(`${EMAIL_URL}/verify`, {
    method: "POST",
    data: { email, otp },
  });
};

export const checkEmail = async (email: string) => {
  return apiCall<{ result: boolean; name?: string }>(SIGNUP_URL, {
    method: "GET",
    params: { p1: email },
  });
};

export const signup = async (
  email: string,
  password: string,
  name: string,
  dept: string,
  verificationToken: string,
) => {
  return apiCall<{ result: boolean; name?: string }>(SIGNUP_URL, {
    method: "POST",
    data: { email, password, name, dept, verificationToken },
  });
};
