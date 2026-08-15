// tests/lib/terminal/candleChartFallbacks.test.ts
//
// `candleChart.ts` 는 CSS 변수를 `getComputedStyle` 로 읽고, 변수가 비어 있을 때 쓸 폴백 채널을
// 소스에 문자열로 갖고 있다. 그 폴백은 `globals.css` 의 다크 토큰과 같아야 하는데, 둘을 잇는
// 것이 주석뿐이라 **토큰만 고치고 폴백을 놓치면 아무도 모른다.**
//
// 실제로 그렇게 어긋났다 — #73 S1 이 `--ink-muted` 를 두 번 옮기는 동안 폴백 하나가 중간
// 값(`185 179 169`)에 남았고, 타입체커·린터·기존 테스트가 전부 초록이었다. 폴백은 변수가 빌
// 때만 쓰이므로 화면에서도 안 드러난다.
//
// 그래서 값 자체를 대조한다. 검사한 짝이 0건이면 실패한다 — 호출 형태가 바뀌어 정규식이 아무것도
// 못 잡으면 "어긋남 없음"이 아니라 "아무것도 안 봤음"이기 때문이다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND = fileURLToPath(new URL("../../../", import.meta.url));

/** `readCssColor(container, "--토큰", "R G B")` 호출에서 (토큰, 폴백) 짝을 뽑는다. */
const READ_CSS_COLOR = /readCssColor\(\s*\w+\s*,\s*"(--[\w-]+)"\s*,\s*"([^"]+)"\s*\)/g;

/** `globals.css` 의 다크 기본 벌 — `:root` 로 시작하는 선택자 목록의 블록. */
function darkTokens(): Map<string, string> {
  const css = readFileSync(`${FRONTEND}styles/globals.css`, "utf-8");
  const tokens = new Map<string, string>();
  for (const [, prelude, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selectors = prelude
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .split(";")
      .at(-1)!
      .split(",")
      .map((s) => s.trim());
    if (!selectors.includes(":root")) continue;
    for (const [, name, value] of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
      tokens.set(name, value.trim());
    }
  }
  return tokens;
}

describe("candleChart 의 폴백 채널값이 globals.css 다크 토큰과 같다", () => {
  it("모든 readCssColor 폴백이 토큰값과 일치한다 — 짝이 0건이면 실패(fail-closed)", () => {
    const source = readFileSync(`${FRONTEND}lib/terminal/candleChart.ts`, "utf-8");
    const pairs = [...source.matchAll(READ_CSS_COLOR)].map(([, token, fallback]) => ({
      token,
      fallback,
    }));

    expect(pairs.length, "readCssColor 호출을 0건 찾았다 — 호출 형태가 바뀌었는지 확인하라").toBeGreaterThan(0);

    const tokens = darkTokens();
    expect(tokens.size, "globals.css 의 :root 토큰을 0건 읽었다").toBeGreaterThan(0);

    for (const { token, fallback } of pairs) {
      const declared = tokens.get(token);
      expect(declared, `${token} 이 globals.css 의 :root 에 없다`).toBeDefined();
      expect(fallback, `${token} 의 폴백이 토큰값과 다르다`).toBe(declared);
    }
  });
});
