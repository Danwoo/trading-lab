import { describe, expect, it } from "vitest";

import { normalizeEmail } from "@/lib/auth/normalizeEmail";

// Better Auth 1.6.11 은 가입·조회 모두 `email.toLowerCase()` 로 저장·매칭한다
// (node_modules/better-auth/dist/api/routes/sign-up.mjs:163). 이 저장소가 이메일을 조회·
// 스코핑·감사컬럼 어디서든 이 함수를 통과한 값만 쓰지 않으면, 대문자로 가입한 사용자를
// 저장 직후부터 못 찾는다 (#250) — 실제로 가입 라우트가 그 결함을 갖고 있었다.
describe("normalizeEmail — 저장·조회 단일 규칙", () => {
  it("대문자 도메인·로컬파트를 소문자로 맞춘다", () => {
    expect(normalizeEmail("Upper@EXAMPLE.COM")).toBe("upper@example.com");
  });

  it("앞뒤 공백을 제거한다 — 주소의 일부가 아니라 입력 사고", () => {
    expect(normalizeEmail("  spaced@example.com  ")).toBe("spaced@example.com");
  });

  it("공백과 대소문자가 함께 섞여도 같은 결과로 수렴한다", () => {
    expect(normalizeEmail("  Mixed.Case@Example.COM ")).toBe("mixed.case@example.com");
  });

  it("이미 정규화된 값은 그대로 돌려준다(멱등)", () => {
    expect(normalizeEmail("already@example.com")).toBe("already@example.com");
  });

  it("서로 다른 대소문자·공백 변형이 전부 같은 정규화 결과로 수렴한다", () => {
    const variants = ["User@Example.com", "USER@EXAMPLE.COM", " user@example.com", "UsEr@exAMPle.CoM  "];
    const normalized = variants.map(normalizeEmail);
    expect(new Set(normalized).size).toBe(1);
    expect(normalized[0]).toBe("user@example.com");
  });
});
