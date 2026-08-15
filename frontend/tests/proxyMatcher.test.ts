// 미들웨어(`proxy.ts`) matcher 회귀 그물 — **보호 밖 페이지 라우트가 0개인가.**
//
// matcher 는 Next 가 빌드 타임에 정적으로 읽어야 해서 상수 import 로 유도할 수 없다(손 목록이다).
// 손 목록은 라우트가 늘어날 때 조용히 뒤처진다 — 빠진 경로는 세션 없이도 페이지가 그대로 열리고
// 데이터 API 만 401 을 내므로 "빈 화면"으로만 드러난다. `/terminal` 이 실제로 그 상태였다(#73 S2).
//
// 이 파일은 `app/**/page.tsx` 전수를 라우트 경로로 환원해 matcher 와 대조한다.
// **fail-closed**: 수집한 라우트가 0건이면(경로 규약이 바뀌어 스캐너가 헛돌면) 실패한다.
// 검사한 건수를 단언에 실어 "위반 없음"과 "아무것도 안 봤음"을 구분할 수 있게 한다.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appDir = path.join(frontendDir, "app");

/**
 * 세션 없이 열려야 하는 페이지 — 로그인·회원가입 흐름.
 *
 * `proxy.ts` 의 `PUBLIC_RULES` 는 API 경로만 다루므로(페이지는 matcher 밖이면 그냥 통과)
 * 페이지 쪽 예외는 여기가 유일한 목록이다. **낡으면 실패한다** — 여기 적힌 접두어에 해당하는
 * 라우트가 더는 없으면 아래 셋째 테스트가 잡는다.
 */
const PUBLIC_PAGE_PREFIXES = [
  "/", // 로그인
  "/signup", // 회원가입·아이디찾기·비밀번호재설정
];

/** `app/(main)/bench/page.tsx` → `/bench`. 라우트 그룹 `(x)` 는 URL 에 안 나온다. */
function toRoutePath(pageFile: string): string {
  const relative = path.relative(appDir, path.dirname(pageFile));
  const segments = relative
    .split(path.sep)
    .filter((s) => s !== "" && s !== ".")
    .filter((s) => !(s.startsWith("(") && s.endsWith(")")));
  return "/" + segments.join("/");
}

function collectPageFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      found.push(...collectPageFiles(full));
    } else if (entry === "page.tsx" || entry === "page.ts") {
      found.push(full);
    }
  }
  return found;
}

const pageRoutes = collectPageFiles(appDir).map(toRoutePath).sort();

/** `"/admin/:path*"` → `/admin` 및 그 하위 전부. Next 의 `:name*` 은 0개 이상 세그먼트다. */
function matcherCovers(pattern: string, route: string): boolean {
  const base = pattern.replace(/\/:[^/]*\*?$/, "");
  return route === base || route.startsWith(base + "/");
}

/** `proxy.ts` 소스에서 matcher 배열을 읽는다 — import 하면 `@/env` 검증이 딸려 온다. */
function readMatcher(): string[] {
  const source = readFileSync(path.join(frontendDir, "proxy.ts"), "utf8");
  const block = /matcher:\s*\[([^\]]*)\]/.exec(source);
  expect(block, "proxy.ts 에서 matcher 배열을 찾지 못했다 — 형식이 바뀌었다").not.toBeNull();
  return Array.from((block as RegExpExecArray)[1].matchAll(/"([^"]+)"/g)).map((m) => m[1]);
}

const matchesPublicPrefix = (route: string, prefix: string) =>
  route === prefix || (prefix !== "/" && route.startsWith(prefix + "/"));

const isPublicPage = (route: string) => PUBLIC_PAGE_PREFIXES.some((prefix) => matchesPublicPrefix(route, prefix));

describe("미들웨어 matcher 가 페이지 라우트를 다 덮는가 (#73 S2)", () => {
  it("스캔 대상이 0건이 아니다", () => {
    // 이 단언이 없으면 아래 두 테스트는 라우트를 하나도 못 찾아도 조용히 통과한다.
    expect(pageRoutes.length, "app/ 아래에서 page.tsx 를 하나도 못 찾았다 — 스캐너가 구조와 어긋났다").toBeGreaterThan(
      10,
    );
    expect(readMatcher().length, "matcher 항목이 0개다").toBeGreaterThan(0);
  });

  it("공개 페이지를 뺀 모든 페이지 라우트가 matcher 안에 있다", () => {
    const matcher = readMatcher();
    const guarded = pageRoutes.filter((route) => !isPublicPage(route));
    expect(guarded.length, "보호 대상 페이지가 0건이다 — 공개 예외 목록이 전부를 삼켰다").toBeGreaterThan(0);

    const uncovered = guarded.filter((route) => !matcher.some((pattern) => matcherCovers(pattern, route)));
    expect(uncovered, `matcher 밖 페이지 라우트: ${uncovered.join(", ") || "없음"}`).toEqual([]);
  });

  it("공개 예외 목록이 낡지 않았다 — 적힌 접두어마다 실재하는 라우트가 있다", () => {
    for (const prefix of PUBLIC_PAGE_PREFIXES) {
      const backing = pageRoutes.filter((route) => matchesPublicPrefix(route, prefix));
      expect(backing.length, `공개 예외 "${prefix}" 에 해당하는 페이지가 더는 없다 — 목록이 낡았다`).toBeGreaterThan(0);
    }
  });
});
