// 셸 폭의 SoT 대조 (§21.6).
//
// 폭·배분을 CSS 로 옮기고 나면 값이 세 군데로 흩어진다 — 화면 결정 §21.6 의 표, `globals.css`
// 의 `--shell-*`, 그리고 구간을 고르는 Tailwind 의 `lg`·`xl`. 어긋나도 화면은 조용히 그려지고
// 「조금 이상한 폭」으로만 나타나므로 사람이 못 잡는다. 여기서 셋을 맞대고, **검사한 건수가
// 기대치와 다르면 실패**시킨다 — 토큰이 사라져도 「위반 0건」으로 초록이 되지 않게.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";
import defaultTheme from "tailwindcss/defaultTheme";

import { theme } from "../../tailwind.config.mjs";
import { VIEWPORT_COMPACT_MIN_PX, VIEWPORT_WIDE_MIN_PX } from "@/constants/shell";

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const GLOBALS_CSS = readFileSync(resolve(FRONTEND_ROOT, "styles/globals.css"), "utf8");

/** 화면 결정 §21.6 의 표가 못박은 값. 여기를 고치려면 그 문서를 먼저 고쳐야 한다. */
const SPEC_WIDTHS = {
  "--shell-rail": "46px",
  "--shell-panel": "372px",
  "--shell-panel-compact": "300px",
  "--shell-panel-expanded": "620px",
} as const;

/** 없으면 던진다 — 「extend 가 사라졌으니 검사할 것도 없다」로 초록이 되면 안 된다. */
function themeExtend(): NonNullable<NonNullable<typeof theme>["extend"]> {
  const extend = theme?.extend;
  if (!extend) throw new Error("tailwind.config.mjs 에 theme.extend 가 없다 — 셸 토큰이 설 자리가 사라졌다.");
  return extend;
}

function declaredShellTokens(): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [, name, value] of GLOBALS_CSS.matchAll(/(--shell-[a-z-]+)\s*:\s*([^;]+);/g)) {
    found[name] = value.trim();
  }
  return found;
}

describe("셸 폭 토큰 — globals.css 가 §21.6 의 값을 갖는다", () => {
  it("네 개가 다 있고 값이 표와 같다 — 하나라도 사라지면 여기서 실패한다", () => {
    const declared = declaredShellTokens();

    expect(Object.keys(declared).sort()).toEqual(Object.keys(SPEC_WIDTHS).sort());
    expect(declared).toEqual(SPEC_WIDTHS);
  });

  it("Tailwind 가 그 네 개를 `w-shell-*` 로 노출한다 — 안 그러면 유틸리티가 조용히 생략된다", () => {
    const spacing = themeExtend().spacing as Record<string, string>;
    const shellKeys = Object.keys(spacing).filter((key) => key.startsWith("shell-"));

    expect(shellKeys.sort()).toEqual(["shell-panel", "shell-panel-compact", "shell-panel-expanded", "shell-rail"]);
    for (const key of shellKeys) {
      expect(spacing[key]).toBe(`var(--${key})`);
    }
  });
});

describe("폭 구간 경계 — CSS 와 JS 가 같은 숫자를 본다", () => {
  it("`lg`·`xl` 이 §21.6 의 1024·1280 이다", () => {
    expect(defaultTheme.screens.lg).toBe(`${VIEWPORT_COMPACT_MIN_PX}px`);
    expect(defaultTheme.screens.xl).toBe(`${VIEWPORT_WIDE_MIN_PX}px`);
    expect(VIEWPORT_COMPACT_MIN_PX).toBe(1024);
    expect(VIEWPORT_WIDE_MIN_PX).toBe(1280);
  });

  it("설정이 `screens` 를 덮지 않는다 — 덮으면 위 대조가 거짓말이 된다", () => {
    expect("screens" in themeExtend()).toBe(false);
  });
});
