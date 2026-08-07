import { z } from "zod";
import { object } from "@/lib/zod/helpers";

/** 가입 폼이 검사하는 필드 — email 은 폼에 없다(OTP 로 먼저 확인한 값을 쓴다). */
export const signupSchema = object({
  password: z.string().min(8, "비밀번호 8자리 이상 입력해주세요.").max(72),
  name: z.string().min(1, "이름을 입력해주세요.").max(100),
  dept: z.string().max(50).optional(),
});

// 라우트(`app/api/common/signup/route.ts`)의 이메일 형식 검사와 같은 정규식이어야 한다 —
// 두 벌이 갈리면 한쪽만 통과하는 값이 생긴다.
export const SIGNUP_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * 요청 경계(POST /api/common/signup)가 검사하는 **전체** 계약 — 폼이 안 보내는 email 까지 포함한다.
 *
 * 클라이언트 검증에만 기대면 API 를 직접 호출했을 때 DB·better-auth 가 대신 던지고, 그것이
 * 500 으로 샌다(#266·#388). 상한은 DB 컬럼과 같은 값이다 (prisma/schema.prisma 의
 * `model User`: email·name VARCHAR(100), dept VARCHAR(50)) — 어긋나면 스키마를 통과한 값이
 * DB 에서 P2000 이 된다. password 의 72는 better-auth 의 상한이다(초과 시 PASSWORD_TOO_LONG).
 */
export const signupRequestSchema = signupSchema.extend({
  email: z.string().trim().max(100).regex(SIGNUP_EMAIL_PATTERN),
});

export type SignupFormData = z.infer<typeof signupSchema>;
