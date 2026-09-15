// @vitest-environment node
//
// 없는 색 토큰을 지어 쓰면 **아무 CSS 와도 매치되지 않아 조용히 색이 빠진다** (#401 리뷰 지적).
//
// 실측: 경고 문구에 `border-warning` 을 썼는데 이 레포의 상태색은 `danger`·`caution`·`success`
// 셋뿐이다. 클래스는 멀쩡히 붙고 `role="alert"` 도 살아 있어 **jsdom 그물은 전부 초록**인데,
// 화면에서는 테두리가 안 그려진다 — 「말하게 한다」가 목적인 변경이 화면에서 안 보이는 문구가 된다.
//
// 이 레포에 같은 유형의 선례가 있다(`border-transparent` 순서 함정 — computed style 로만 드러났다).
// 브라우저 없이 잡을 수 있는 몫이 여기다: **상태색으로 읽히는 이름을 썼으면 선언돼 있어야 한다.**
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");
const SCANNED = ["components", "app", "lib", "utils"];

/** 상태를 말하려고 쓰는 이름들 — 선언 없이 쓰면 색이 통째로 빠진다. */
const STATE_WORDS = ["danger", "caution", "success", "warning", "error", "info", "alert", "critical"];
/** 색을 받는 유틸리티 접두사 */
const UTILITIES = ["border", "text", "bg", "ring", "outline", "fill", "stroke", "decoration", "shadow", "accent"];

const USE = new RegExp(`\\b(${UTILITIES.join("|")})-(${STATE_WORDS.join("|")})\\b`, "g");

function sourceFiles(dir: string): string[] {
  let found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) found = found.concat(sourceFiles(full));
    else if (/\.(tsx?|css)$/.test(entry.name)) found.push(full);
  }
  return found;
}

function declaredColors(): Set<string> {
  const config = readFileSync(path.join(ROOT, "tailwind.config.mjs"), "utf-8");
  return new Set([...config.matchAll(/^\s*([a-z][a-zA-Z0-9]*):\s*"rgb\(var\(--/gm)].map((m) => m[1]));
}

describe("상태색 이름은 선언된 것만 쓴다", () => {
  const declared = declaredColors();
  const files = SCANNED.flatMap((dir) => sourceFiles(path.join(ROOT, dir)));

  it("tailwind 설정에서 색 이름을 실제로 읽었다 — 0개면 판독이 깨진 것이다", () => {
    expect(declared.size).toBeGreaterThan(3);
    expect(declared.has("danger")).toBe(true);
    expect(declared.has("caution")).toBe(true);
  });

  it("훑을 파일이 있다 — 0건은 통과가 아니다", () => {
    expect(files.length).toBeGreaterThan(100);
  });

  it("선언되지 않은 상태색을 쓴 자리가 없다", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const text = readFileSync(file, "utf-8");
      for (const match of text.matchAll(USE)) {
        if (!declared.has(match[2])) {
          offenders.push(`${path.relative(ROOT, file)}: ${match[0]}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
