// tests/styles/tailwindOpacityModifier.test.ts
//
// #313 회귀 그물 — 팔레트 토큰(bg·line·btn·ink·market·상태색, `tailwind.config.mjs`)에 opacity
// modifier(`/40` 등)를 붙인 유틸리티가 실제 CSS 로 생성되는지 검사한다.
//
// var() 문자열 그대로 정의된 색은 Tailwind v3 가 modifier 유틸리티를 조용히 생략한다 — 빌드도
// 린트도 통과하고 화면에서만 테두리·배경 틴트가 사라진다(이슈 원문 실측: TerminalContainer.tsx
// 의 복구 알림 띠에서 테두리·배경 틴트가 통째로 사라졌다). 이 테스트가 없으면 같은 방식으로
// 다시 죽어도 아무도 모른다.
import { describe, expect, it } from "vitest";
import postcss, { type Rule } from "postcss";
import tailwindcss from "tailwindcss";
import * as tailwindConfig from "@/tailwind.config.mjs";

// 팔레트 전량 x opacity modifier 1건씩 — 지금 화면이 실제로 쓰는 조합만이 아니라
// "앞으로 쓸 수 있는" 조합 전체를 검사한다(클래스를 닫는다는 이슈의 취지).
// 디자인 시스템 토큰(#73 S1)이 전부다 — 레거시 토큰(#242 O3)은 S5 가 팔레트에서 지웠다.
const COLOR_UTILITIES = [
  "bg-bg-base/40",
  "bg-bg-panel/60",
  "bg-bg-raised/30",
  "border-hairline/50",
  "border-line/60",
  "border-line-strong/40",
  "bg-btn-from/80",
  "bg-btn-to/80",
  "border-btn-line/40",
  "text-ink/90",
  "text-ink-strong/80",
  "text-ink-muted/30",
  "text-ink-faint/70",
  "text-danger/60",
  "bg-danger/10",
  "text-success/60",
  "bg-success/10",
  "text-market-up/50",
  "bg-market-down/25",
];

async function compileUtilities(classNames: string[]): Promise<Rule[]> {
  const config = {
    content: [{ raw: classNames.join(" "), extension: "html" }],
    theme: tailwindConfig.theme,
    plugins: tailwindConfig.plugins,
  };
  const result = await postcss([tailwindcss(config)]).process("@tailwind utilities;", {
    from: undefined,
  });
  const root = postcss.parse(result.css);
  const rules: Rule[] = [];
  root.walkRules((rule) => {
    rules.push(rule);
  });
  return rules;
}

/** Tailwind 가 이스케이프한 셀렉터(`.bg-bg-panel\/60`)를 원래 클래스명으로 되돌린다. */
function unescapeSelector(selector: string): string {
  return selector.replace(/^\./, "").replace(/\\(.)/g, "$1");
}

describe("Tailwind 색 토큰의 opacity modifier — CSS 생성 여부 (#313 회귀 그물)", () => {
  it(`팔레트 ${COLOR_UTILITIES.length}개 전부가 실제 CSS 선언을 낸다 — 0건이면 실패(fail-closed)`, async () => {
    const rules = await compileUtilities(COLOR_UTILITIES);
    const byClassName = new Map(rules.map((rule) => [unescapeSelector(rule.selector), rule]));

    let matched = 0;
    for (const className of COLOR_UTILITIES) {
      const rule = byClassName.get(className);
      expect(rule, `${className} 에 대응하는 CSS 규칙이 생성되지 않았다`).toBeTruthy();
      expect(rule!.nodes.length, `${className} 규칙에 선언이 없다`).toBeGreaterThan(0);
      matched += 1;
    }

    // 검사 대상 0건이면 통과가 아니라 실패 — 이 숫자가 COLOR_UTILITIES.length 와 다르면
    // "위반 없음"이 아니라 "테스트가 아무것도 못 봤음"일 수 있다.
    expect(matched).toBe(COLOR_UTILITIES.length);
  });

  it("생성된 선언이 rgb(var(...) / alpha) 형태다 — var() 단독 문자열로 되돌아가면 비어야 정상", async () => {
    const rules = await compileUtilities(["bg-bg-panel/60"]);
    const rule = rules.find((r) => unescapeSelector(r.selector) === "bg-bg-panel/60");
    expect(rule).toBeTruthy();
    expect(rule!.toString()).toMatch(/rgb\(var\(--bg-panel\)\s*\/\s*0\.6\)/);
  });
});
