// #317 — **화면이 가리키는 다음 걸음의 목적지가 실제로 열려 있어야 한다.**
//
// 이슈가 실측으로 잡은 것 셋 중 둘이 「가리키는 곳이 없다」였다: 「포트폴리오 화면에서 먼저
// 등록하세요」가 가리킨 레일 항목은 `constants/shell.ts` 에서 **준비 중**이고, 「.env 를
// 채우세요」는 화면이 아니라 파일을 가리켰다(그 일을 하는 `/settings` 가 이미 있는데도).
//
// 손으로 훑는 것으로는 이 클래스가 닫히지 않는다 — 레일 항목이 준비 중으로 바뀌는 것과 그 이름을
// 부르는 문구가 서로 다른 파일에 있어서다. 그래서 두 축을 정적으로 잡는다:
//
//   ① **준비 중인 레일 항목을 목적지로 부르지 않는다** — `constants/shell.ts` 의 `pending` 이
//      정본이다. 화면이 붙어 `pending` 이 사라지면 이 그물은 그 이름을 자동으로 놓아 준다.
//   ② **링크의 목적지가 실재한다** — 화면이 주는 `href` 상수·리터럴이 `app/` 의 라우트로
//      풀려야 한다. 라우트 그룹`(main)`은 주소에 안 나오므로 벗겨서 대조한다.
//
// **fail-closed**: 준비 중 항목이 0건이거나 훑은 파일이 적으면 실패한다 — 파싱이 조용히 빗나가
// "위반 없음"으로 초록이 되는 것을 막는다.
//
// **검증 경계** — 정적 검사다. 그 링크를 눌러 화면이 실제로 뜨는지는 보지 않는다(그건 브라우저로
// 확인한다). 문장 속에서 이름만 스치는 언급(주석·문서)도 보지 않는다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** 화면 문구와 링크가 만들어지는 계층. `api` 는 서버 라우트라 대상이 아니다. */
const SCANNED_DIRS = ["components", "hooks", "app", "constants"];
const SKIP_DIRS = new Set(["api"]);

/** 라우트가 아닌 정적 자산 — `<link rel="icon">` 같은 것. */
const NOT_A_ROUTE = /\.(ico|png|svg|jpg|webp|txt|xml|json)$/;

function walk(dir: string): string[] {
  const entries = fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : [];
  return entries.flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return SKIP_DIRS.has(entry.name) ? [] : walk(full);
    return /\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

function scannedFiles(): string[] {
  return SCANNED_DIRS.flatMap((dir) => walk(path.join(FRONTEND_ROOT, dir)));
}

/** 주석 줄은 화면에 안 나간다 — 규칙 자체를 설명하는 문장이 위반으로 잡히지 않게 뺀다. */
function isComment(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*");
}

/** `constants/shell.ts` 의 레일 항목 — `pending` 이 있는 것이 「아직 못 여는 자리」다. */
function railItems(): Array<{ label: string; pending: boolean }> {
  const source = fs.readFileSync(path.join(FRONTEND_ROOT, "constants/shell.ts"), "utf8");
  const array = source.slice(source.indexOf("export const RAIL_ITEMS"));
  return [...array.matchAll(/\{[^{}]*\}/g)].flatMap((match) => {
    const label = match[0].match(/label:\s*"([^"]+)"/);
    return label ? [{ label: label[1], pending: /\bpending:/.test(match[0]) }] : [];
  });
}

/** `app/` 이 실제로 여는 주소 — 라우트 그룹은 벗기고 동적 구간은 패턴으로 남긴다. */
function routePatterns(): RegExp[] {
  const appRoot = path.join(FRONTEND_ROOT, "app");
  const pages: string[] = [];
  const collect = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) collect(full);
      else if (entry.name === "page.tsx") pages.push(path.relative(appRoot, dir));
    }
  };
  collect(appRoot);
  return pages.map((page) => {
    const segments = page
      .split(path.sep)
      .filter((segment) => segment !== "" && !segment.startsWith("("))
      .map((segment) => (segment.startsWith("[") ? "[^/]+" : segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    return new RegExp(`^/${segments.join("/")}$`.replace("^//$", "^/$"));
  });
}

/** 화면이 주는 링크 — `href="/x"`·`href: "/x"` 리터럴과 `constants/routes.ts` 의 경로 상수. */
function declaredHrefs(): Array<{ where: string; href: string }> {
  const out: Array<{ where: string; href: string }> = [];
  for (const file of scannedFiles()) {
    const rel = path.relative(FRONTEND_ROOT, file);
    fs.readFileSync(file, "utf8")
      .split("\n")
      .forEach((line, i) => {
        if (isComment(line)) return;
        for (const match of line.matchAll(/href[:=]\s*\{?"(\/[^"$]*)"/g)) {
          out.push({ where: `${rel}:${i + 1}`, href: match[1] });
        }
      });
  }
  const routesFile = path.join(FRONTEND_ROOT, "constants/routes.ts");
  fs.readFileSync(routesFile, "utf8")
    .split("\n")
    .forEach((line, i) => {
      const match = line.match(/^export const (\w*PATH)\s*=\s*"(\/[^"]*)"/);
      if (match) out.push({ where: `constants/routes.ts:${i + 1} (${match[1]})`, href: match[2] });
    });
  return out;
}

describe("#317 화면이 가리키는 목적지가 열려 있다", () => {
  it("훑을 대상이 있다 — 파싱이 빗나가면 조용히 초록이 되지 않게", () => {
    const items = railItems();
    expect(items.length).toBeGreaterThan(5);
    expect(items.filter((item) => item.pending).length).toBeGreaterThan(0);
    expect(scannedFiles().length).toBeGreaterThan(50);
    expect(routePatterns().length).toBeGreaterThan(5);
    expect(declaredHrefs().length).toBeGreaterThan(5);
  });

  it("아직 못 여는 레일 항목을 목적지로 부르지 않는다", () => {
    const pendingLabels = railItems()
      .filter((item) => item.pending)
      .map((item) => item.label);
    // 「<이름> 화면에서 …」·「<이름> 패널로 …」 처럼 **그 자리로 가라**고 읽히는 모양만 잡는다.
    // 이름 자체를 스치는 문장(제목·설명)은 목적지 지시가 아니다.
    const points = new RegExp(`(${pendingLabels.join("|")})\\s*(화면|패널|메뉴)\\s*(에서|으로|에)`);
    const offenders: string[] = [];

    for (const file of scannedFiles()) {
      const rel = path.relative(FRONTEND_ROOT, file);
      fs.readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (isComment(line)) return;
          if (points.test(line)) offenders.push(`${rel}:${i + 1} — ${line.trim()}`);
        });
    }

    expect(offenders).toEqual([]);
  });

  it("화면이 주는 링크는 전부 실재하는 라우트다", () => {
    const patterns = routePatterns();
    const dead = declaredHrefs().filter(({ href }) => {
      if (NOT_A_ROUTE.test(href)) return false;
      const pathOnly = href.split(/[?#]/)[0];
      return !patterns.some((pattern) => pattern.test(pathOnly));
    });

    expect(dead).toEqual([]);
  });
});
