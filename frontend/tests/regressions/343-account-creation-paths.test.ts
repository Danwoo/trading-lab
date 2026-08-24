// #343 — **계정을 만드는 경로의 전수 대조 그물.**
//
// 이슈가 지목한 결함은 "가입 API 에 인증 검사가 없다"였지만, 진짜 클래스는 **계정을 만드는
// 자리가 여러 개인데 각자의 문지기를 아무도 세지 않는다**는 것이다. 새 경로가 하나 생기고
// 문지기를 빠뜨려도 기존 테스트는 전부 초록이다.
//
// 그래서 이 파일은 소스를 **훑어서** 계정 생성 경로를 찾고, 찾은 것 전부가 아래 표에 있고
// 표에 적힌 문지기를 실제로 달고 있는지 대조한다. 표에 없는 경로가 나오면 실패하고, 표에
// 있는데 소스에서 사라져도 실패한다 — 어느 방향이든 사람이 다시 판정해야 한다.
//
// **fail-closed**: 훑어서 찾은 경로가 0건이면 실패한다. 0건은 "위반 없음"이 아니라
// "아무것도 안 봤음"이고, 그 둘을 못 가르는 초록은 죽은 그물이다.
//
// 여기서 보는 것은 **문지기가 달려 있는가**(구조)다. 그 문지기가 실제로 막는가(행동)는
// `343-signup-requires-verification.test.ts` 가 라우트를 직접 호출해 확인한다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** Better Auth 로 사용자를 만드는 호출. 이 문자열이 있는 라우트가 곧 계정 생성 경로다. */
const CREATE_CALL = "auth.api.signUpEmail";

/**
 * 계정 생성 경로와 그 문지기 — **경로마다 하나씩 판정한 결과**다.
 * 새 경로를 여기 더할 때는 "무엇이 이 경로를 지키는가"를 같이 적는다.
 */
const ACCOUNT_CREATION_PATHS: ReadonlyArray<{ file: string; gate: string; why: string }> = [
  {
    file: "app/api/common/signup/route.ts",
    // 이메일 소유 증명이 문지기다 — OTP 를 맞혔다는 서버 증거를 소비해야 계정이 만들어진다.
    // 문자열이 아니라 **호출 형태**를 본다 — 이름만 보면 쓰지 않는 import 하나로도 통과한다
    // (실측: 관문 본문만 지우고 import 를 남긴 돌연변이가 이 그물을 초록으로 지나갔다).
    gate: "await consumeSignupVerificationGrant(email, verificationToken)",
    why: "공개 가입 — 세션이 없으므로 이메일 소유 증명이 유일한 문지기다 (#343)",
  },
  {
    file: "app/api/common/system/adminuser/route.ts",
    // 관리자·운영자 권한이 문지기다 — 이 경로가 만드는 계정은 만든 사람의 권한으로 정당화된다.
    gate: "requireOperatorOrAdmin: true",
    why: "관리자 생성 — 이메일 소유가 아니라 만드는 사람의 권한이 근거다",
  },
];

function listRouteFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) listRouteFiles(full, out);
    else if (entry.name === "route.ts") out.push(path.relative(FRONTEND_ROOT, full));
  }
  return out;
}

const routeFiles = listRouteFiles(path.join(FRONTEND_ROOT, "app", "api"));
const creationRoutes = routeFiles
  .filter((rel) => fs.readFileSync(path.join(FRONTEND_ROOT, rel), "utf8").includes(CREATE_CALL))
  .sort();

describe("#343 계정을 만드는 경로 전수", () => {
  it(`라우트를 훑어 계정 생성 경로를 찾았다 (route.ts ${routeFiles.length}개 중 ${creationRoutes.length}개)`, () => {
    // 0건은 통과가 아니다 — 훑기가 죽었거나 호출 형태가 바뀐 것이다.
    expect(routeFiles.length).toBeGreaterThan(0);
    expect(creationRoutes.length).toBeGreaterThan(0);
    console.info(
      `[#343] route.ts ${routeFiles.length}개를 훑어 \`${CREATE_CALL}\` 호출 ${creationRoutes.length}개를 검사했다: ${creationRoutes.join(", ")}`,
    );
  });

  it("찾은 경로와 판정표가 정확히 일치한다 (표에 없는 새 경로도, 사라진 경로도 실패)", () => {
    expect(creationRoutes).toEqual([...ACCOUNT_CREATION_PATHS.map((p) => p.file)].sort());
  });

  it.each(ACCOUNT_CREATION_PATHS)("$file 은 $gate 로 지켜진다 — $why", ({ file, gate }) => {
    expect(fs.readFileSync(path.join(FRONTEND_ROOT, file), "utf8")).toContain(gate);
  });
});

describe("#343 Better Auth 가 딸려 노출하는 가입 엔드포인트는 바깥에 열려 있지 않다", () => {
  it("proxy.ts 의 공개 목록에 /api/auth/sign-up 이 없다", () => {
    const proxy = fs.readFileSync(path.join(FRONTEND_ROOT, "proxy.ts"), "utf8");
    // 주석이 아니라 규칙 줄만 본다 — `{ path: "/api/auth/sign-up/" ... }` 형태.
    const publicRulePaths = [...proxy.matchAll(/\{\s*path:\s*"([^"]+)"/g)].map((m) => m[1]);
    expect(publicRulePaths.length).toBeGreaterThan(0);
    expect(publicRulePaths).not.toContain("/api/auth/sign-up/");
    expect(publicRulePaths.filter((p) => p.startsWith("/api/auth/sign-up"))).toEqual([]);
  });

  it("auth.ts 가 HTTP 로 들어온 /sign-up/email 을 hooks.before 에서 막는다", () => {
    const authTs = fs.readFileSync(path.join(FRONTEND_ROOT, "lib", "auth", "auth.ts"), "utf8");
    expect(authTs).toContain('ctx.path === "/sign-up/email"');
    expect(authTs).toMatch(/hooks:\s*\{\s*\n\s*before:/);
  });
});
