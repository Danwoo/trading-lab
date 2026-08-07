import { apiCall } from "@/utils/common/api/client";

const EMAIL_URL = "/api/common/email";
const SIGNUP_URL = "/api/common/signup";

export const sendEmail = async (to: string) => {
  return apiCall<{ message: string }>(EMAIL_URL, {
    method: "POST",
    data: { to },
  });
};

export const verifySignupOTP = async (email: string, otp: string) => {
  return apiCall<{ result: boolean }>(`${EMAIL_URL}/verify`, {
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

export const signup = async (email: string, password: string, name: string, dept: string) => {
  return apiCall<{ result: boolean; name?: string }>(SIGNUP_URL, {
    method: "POST",
    data: { email, password, name, dept },
  });
};
