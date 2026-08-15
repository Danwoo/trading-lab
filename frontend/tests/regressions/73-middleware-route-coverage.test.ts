// #73 S2 회귀 그물 — **미들웨어 밖에 남은 화면이 있는가.**
//
// `proxy.ts` 의 `config.matcher` 는 allowlist 다. 새 화면을 거기 넣지 않으면 그 경로는 세션
// 확인 없이 그냥 열리고, **아무도 빨간불을 보지 못한다**. 실제로 `/terminal` 이 그 상태였다
// (#73 S2 착수 시점 실측 — matcher 는 `/api`·`/admin`·`/user` 뿐이었다).
//
// 이 파일은 `app/` 의 페이지 라우트를 **전수로 세어** 공개 경로가 아닌 것이 전부 matcher 에
// 덮이는지 본다. 검사 대상이 0건이면(글롭이 깨졌거나 디렉터리가 옮겨졌으면) 실패한다.
//
// **검증 경계**: 라우트가 matcher 에 잡히는지만 본다 — 미들웨어 본문이 그 요청에 무엇을 하는지
// (쿠키 검사·리다이렉트)는 보지 않는다.
import { readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

vi.mock("@/env", () => ({ env: { APP_KEY: "test-app" } }));

const { config } = await import("@/proxy");

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const appDir = path.join(frontendDir, "app");

/**
 * 공개 경로 — 세션 없이 열려야 하는 화면. 로그인 화면 자신과 가입 흐름이다.
 * 여기 넣는 것은 **의도적으로 보호를 빼는 것**이므로 새로 넣을 때 근거가 필요하다.
 */
const PUBLIC_ROUTES = new Set(["/", "/signup"]);
const PUBLIC_PREFIXES = ["/signup/"];

/** `app/` 아래 `page.tsx` 를 전부 찾아 URL 경로로 바꾼다(라우트 그룹 `(x)` 는 URL 에 안 나온다). */
function collectPageRoutes(dir: string, urlSegments: string[] = []): string[] {
  const routes: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const isRouteGroup = entry.name.startsWith("(") && entry.name.endsWith(")");
      routes.push(
        ...collectPageRoutes(path.join(dir, entry.name), isRouteGroup ? urlSegments : [...urlSegments, entry.name]),
      );
    } else if (entry.name === "page.tsx") {
      routes.push("/" + urlSegments.join("/"));
    }
  }
  return routes;
}

/** Next.js matcher 패턴(`/admin/:path*`)을 정규식으로. */
function matcherToRegExp(pattern: string): RegExp {
  return new RegExp("^" + pattern.replace(/\/:path\*/g, "(?:/.*)?").replace(/\/:path\+/g, "/.+") + "$");
}

const pageRoutes = collectPageRoutes(appDir).sort();
const isPublic = (route: string) => PUBLIC_ROUTES.has(route) || PUBLIC_PREFIXES.some((p) => route.startsWith(p));
const isMatched = (route: string) => config.matcher.some((pattern) => matcherToRegExp(pattern).test(route));

describe("미들웨어 경로 커버리지 (#73)", () => {
  it(`검사 대상 ${pageRoutes.length}건(공개 ${pageRoutes.filter(isPublic).length}건) — 0건이면 그물이 죽은 것이다`, () => {
    expect(pageRoutes.length, "app/ 에서 page.tsx 를 하나도 못 찾았다 — 경로 규약이 바뀐 것이다").toBeGreaterThan(10);
    expect(pageRoutes, "로그인 화면(/)이 목록에 없다 — 수집이 깨졌다").toContain("/");
  });

  it("공개 경로가 아닌 페이지는 전부 matcher 에 덮인다", () => {
    const uncovered = pageRoutes.filter((route) => !isPublic(route) && !isMatched(route));
    expect(uncovered, `미들웨어 밖 화면: ${uncovered.join(", ")}`).toEqual([]);
  });

  it("제품 셸의 두 목적지가 실제로 덮인다", () => {
    // `PRODUCT_PATHS` 의 리터럴 대조 — 상수만 늘리고 matcher 를 안 늘리는 실수를 잡는다.
    expect(isMatched("/bench")).toBe(true);
    expect(isMatched("/terminal")).toBe(true);
  });

  it("공개 경로 목록이 실제 라우트와 어긋나지 않는다", () => {
    // 없어진 화면을 공개 목록에 남겨 두면, 나중에 그 경로가 다른 화면으로 되살아날 때
    // 보호가 빠진 채로 열린다.
    const stale = [...PUBLIC_ROUTES].filter((route) => !pageRoutes.includes(route));
    expect(stale, `공개 목록에만 있고 실제로는 없는 경로: ${stale.join(", ")}`).toEqual([]);
  });
});
