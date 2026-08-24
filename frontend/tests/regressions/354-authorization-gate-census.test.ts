/**
 * #354 정적 그물 — **인가 게이트가 한 곳뿐이고, 그 한 곳이 쿠키 캐시를 우회하는가.**
 *
 * 결함의 구조: Better Auth 의 쿠키 캐시(JWE)는 세션을 서명된 쿠키에서 복원한다. 그래서 세션
 * 행을 지우는 무효화(권한 회수·계정 비활성·관리자 강제 종료·비밀번호 재설정)가 캐시 수명만큼
 * 통째로 무시된다 — 실측으로 권한 회수 뒤 203초, 강제 종료 뒤 213초, 계정 비활성 뒤 276초까지
 * 200 이 나왔다.
 *
 * 이 그물이 지키는 두 성질:
 * 1. `auth.api.getSession` 호출부가 `withAuth` 하나뿐이다 — 두 번째가 생기면 그쪽이 캐시를
 *    그대로 믿는 새 우회로가 된다. 그래서 "고친 자리"가 아니라 **자리의 개수**를 잠근다.
 * 2. 그 호출이 `disableCookieCache` 를 켠다 — 지우면 결함이 그대로 돌아온다.
 *
 * 그리고 권한 회수 경로가 세션 무효화를 부르는지도 함께 센다 — 사용자 단위 회수는 부르는데
 * 권한 통째 삭제(`DELETE /api/common/system/author/[author_id]`)만 안 불렀다.
 *
 * **fail-closed**: 스캔 대상이 0건이면 실패한다. 검사한 파일 수를 출력에 남겨, 통과가
 * "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있게 한다.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** 스캔 대상 — 서버에서 도는 소스 전부. `tests/` 는 대역을 세우므로 제외한다. */
const SCAN_ROOTS = ["app", "lib", "components", "utils", "hooks", "services", "stores"];

function listSourceFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === "generated") continue;
      out.push(...listSourceFiles(full));
    } else if (entry.isFile() && /\.(ts|tsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function allScannedFiles(): string[] {
  const files = SCAN_ROOTS.flatMap((root) => listSourceFiles(path.join(FRONTEND_ROOT, root)));
  files.push(path.join(FRONTEND_ROOT, "proxy.ts"));
  return files.filter((f) => fs.existsSync(f));
}

const rel = (f: string) => path.relative(FRONTEND_ROOT, f).split(path.sep).join("/");

describe("#354 인가 게이트는 하나뿐이고 쿠키 캐시를 우회한다", () => {
  const files = allScannedFiles();

  it("스캔 대상이 0건이 아니다", () => {
    console.info(`[#354 census] 스캔한 소스 파일: ${files.length}개 (${SCAN_ROOTS.join(", ")}, proxy.ts)`);
    expect(files.length).toBeGreaterThan(0);
  });

  it("서버 세션을 읽는 자리는 lib/auth/withAuth.ts 하나뿐이다", () => {
    const callSites = files.filter((f) => /\bapi\s*\.\s*getSession\s*\(/.test(fs.readFileSync(f, "utf-8"))).map(rel);
    console.info(
      `[#354 census] auth.api.getSession 호출부: ${callSites.length}개 — ${callSites.join(", ") || "(없음)"}`,
    );
    expect(callSites).toEqual(["lib/auth/withAuth.ts"]);
  });

  it("그 호출이 disableCookieCache 를 켠다", () => {
    const src = fs.readFileSync(path.join(FRONTEND_ROOT, "lib/auth/withAuth.ts"), "utf-8");
    const call = /api\s*\.\s*getSession\s*\(\s*\{[\s\S]*?\n\s*\}\s*\)/.exec(src);
    expect(call, "withAuth 안에서 auth.api.getSession 호출을 못 찾았다").not.toBeNull();
    expect(call![0]).toMatch(/disableCookieCache:\s*true/);
  });
});

describe("#354 권한 멤버십을 지우는 라우트는 세션도 무효화한다", () => {
  const routeFiles = listSourceFiles(path.join(FRONTEND_ROOT, "app/api")).filter(
    (f) => path.basename(f) === "route.ts",
  );

  it("스캔 대상이 0건이 아니다", () => {
    console.info(`[#354 census] 스캔한 API 라우트 파일: ${routeFiles.length}개`);
    expect(routeFiles.length).toBeGreaterThan(0);
  });

  it("authorMember 를 지우는 라우트는 전부 세션 무효화를 부른다", () => {
    const revoking: string[] = [];
    const missing: string[] = [];
    for (const file of routeFiles) {
      const src = fs.readFileSync(file, "utf-8");
      if (!/authorMember\s*\.\s*(delete|deleteMany)\s*\(/.test(src)) continue;
      revoking.push(rel(file));
      // **호출**을 찾는다 — `import { invalidateSessionsForUsers }` 는 이름만 있고 부르지는
      // 않으므로 여는 괄호를 요구한다. 이름만 봤을 때는 호출을 지워도 import 가 남아 그물이
      // 초록이었다(돌연변이 시험에서 실제로 통과했다).
      if (!/invalidate(UserSessions|SessionsForUsers)\s*\(/.test(src)) missing.push(rel(file));
    }
    console.info(`[#354 census] authorMember 를 지우는 라우트: ${revoking.length}개 — ${revoking.join(", ")}`);
    expect(revoking.length).toBeGreaterThan(0);
    expect(missing).toEqual([]);
  });
});
