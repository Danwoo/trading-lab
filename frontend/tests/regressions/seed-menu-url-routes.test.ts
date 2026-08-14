// 회귀 그물 — **시드 메뉴의 `url` 이 실재하는 라우트를 가리키는가.**
//
// 결함(수정 전): 화면을 지우고 옮기면서 `prisma/init/seed.sql` 의 메뉴 행이 따라오지 않아,
// 사이드바가 없는 경로로 보냈다. 살려 두기로 한 스케줄러(mbiz1005)는 `admin/devactivity/scheduler`
// 를 계속 가리켰고 그 화면의 유일한 진입점이 404 였다
// (https://github.com/Danwoo/trading-lab/pull/68 리뷰가 잡았다).
//
// 도달 경로: 시드 `url` → `app/api/common/system/menu/navigation/route.ts` 가 `/${url}` 로 path 합성
//         → `components/shared/Layout/Sidebar.tsx` 가 그 path 로 `router.replace`.
// 중간에 재작성(rewrites·redirects·catch-all)이 없어 URL 문자열이 곧 라우트여야 한다.
//
// **검증 경계**: 파일 트리 대조다 — 라우트가 렌더되는지·권한이 통과하는지는 보지 않는다.
// 동적 세그먼트(`[id]`)는 메뉴 url 이 쓰지 않으므로 정확 일치만 본다.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// ── 시드 메뉴 (기본 데이터의 단일 출처) ────────────────────────────────────────

const seedSql = readFileSync(path.join(frontendDir, "prisma/init/seed.sql"), "utf8");

const menuValues = /INSERT INTO tn_menu\b[\s\S]*?VALUES([\s\S]*?);/i.exec(seedSql);

const seedMenus = Array.from(
  (menuValues?.[1] ?? "").matchAll(
    /\('([^']+)', *'([^']*)', *(?:NULL|'[^']*'), *(\d+), *\d+, *'([YN])', *(NULL|'[^']*')/g,
  ),
).map((m) => ({
  menu_id: m[1],
  menu_nm: m[2],
  menu_level: Number(m[3]),
  use_at: m[4],
  url: m[5] === "NULL" ? null : m[5].slice(1, -1),
}));

/** 메뉴 부여 테이블(`(주체, menu_id, …)`)에서 두 번째 컬럼인 menu_id 를 뽑는다. */
function grantedMenuIds(table: string): string[] {
  const block = new RegExp(`INSERT INTO ${table}\\b[\\s\\S]*?VALUES([\\s\\S]*?);`, "i").exec(seedSql);
  expect(block, `seed.sql 에서 ${table} INSERT 블록을 찾지 못했다`).not.toBeNull();
  return Array.from((block as RegExpExecArray)[1].matchAll(/\((?:\d+|'[^']+'), *'([^']+)'/g)).map((m) => m[1]);
}

// ── 실재하는 라우트 (app 디렉터리) ─────────────────────────────────────────────

/** `app/**` 의 page.tsx 를 URL 경로로 바꾼다 — 라우트 그룹 `(main)` 은 URL 에 안 나타난다. */
function collectRoutes(dir: string, segments: string[] = []): string[] {
  const routes: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const isRouteGroup = entry.name.startsWith("(") && entry.name.endsWith(")");
      routes.push(...collectRoutes(path.join(dir, entry.name), isRouteGroup ? segments : [...segments, entry.name]));
    } else if (entry.name === "page.tsx") {
      routes.push(segments.join("/"));
    }
  }
  return routes;
}

const routes = new Set(collectRoutes(path.join(frontendDir, "app")));

describe("시드 메뉴 url ↔ 라우트 대조", () => {
  it("파서가 시드·라우트를 실제로 읽었다", () => {
    expect(menuValues, "seed.sql 에서 tn_menu INSERT 블록을 찾지 못했다").not.toBeNull();
    expect(seedMenus.length, "seed.sql 에서 파싱한 메뉴가 0건이다 — 파서가 시드 형식과 어긋났다").toBeGreaterThan(5);
    expect(routes.size, "app/ 에서 찾은 라우트가 0건이다 — 스캐너가 트리와 어긋났다").toBeGreaterThan(5);
  });

  it("사용 중인 메뉴의 url 이 전부 실재하는 라우트다", () => {
    const linked = seedMenus.filter((m) => m.use_at === "Y" && m.url !== null);

    // 검사 대상이 0건이면 이 단언은 아무것도 안 본 채 초록이 된다 — 그것부터 막는다.
    expect(linked.length, "url 을 가진 사용 중 메뉴가 0건이다").toBeGreaterThan(5);

    for (const menu of linked) {
      expect(
        routes.has(menu.url as string),
        `${menu.menu_id}(${menu.menu_nm}) 의 url '${menu.url}' 에 해당하는 page.tsx 가 없다 — 사이드바가 404 로 보낸다`,
      ).toBe(true);
    }
  });

  it("메뉴 권한 부여가 실재하는 메뉴를 가리킨다 — url 만 고치고 부여 행이 옛 ID 를 가리키면 여전히 안 보인다", () => {
    const menuIds = new Set(seedMenus.map((m) => m.menu_id));
    const grants = [
      ...grantedMenuIds("tn_workspace_menu").map((menu_id) => ({ table: "tn_workspace_menu", menu_id })),
      ...grantedMenuIds("tn_author_menu").map((menu_id) => ({ table: "tn_author_menu", menu_id })),
    ];

    expect(grants.length, "메뉴 부여 행이 0건이다 — 파서가 시드 형식과 어긋났다").toBeGreaterThan(5);

    for (const grant of grants) {
      expect(menuIds.has(grant.menu_id), `${grant.table} 이 tn_menu 에 없는 ${grant.menu_id} 를 부여한다`).toBe(true);
    }
  });

  it("메뉴는 leaf(level 2)만 url 을 갖는다 — 대분류는 펼치기용이라 이동 경로가 없다", () => {
    for (const menu of seedMenus.filter((m) => m.menu_level === 1)) {
      expect(menu.url, `대분류 ${menu.menu_id} 에 url 이 붙어 있다`).toBeNull();
    }
  });
});
