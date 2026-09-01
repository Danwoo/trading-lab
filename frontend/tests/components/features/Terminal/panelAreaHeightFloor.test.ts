// 패널 영역은 0 으로 접히면 안 된다 (#289).
//
// ## 무엇을 지키나
//
// `TerminalContainer` 의 패널 줄은 `overflow-auto` 스크롤러를 담는다. 그 줄이 `min-h-0 flex-1`
// 이면 **위 형제(적재 콘솔)가 화면보다 높아질 때 0 으로 접힌다.** 그러면 스크롤러의 클립 상자가
// 비어 그 안의 조작부가 전부 히트 테스트에서 사라진다 — 크기는 24×24 그대로이고
// `getBoundingClientRect()` 도 화면 안 좌표를 내는데, 그 좌표를 찍으면 `MAIN` 이 잡힌다.
// 실측(폭 390, 로컬 스택): `⋮` rect=349,832,24,24 인데 `elementFromPoint(361,844)` → `MAIN`,
// `page.mouse.click(361,844)` 로 메뉴가 안 열렸다. 하한을 준 뒤 같은 자리에서 열린다.
//
// ## 이 검사의 한계 — 소스 문자열이지 레이아웃 측정이 아니다
//
// 접힘은 **조립된 페이지에서만** 나타난다: 적재 콘솔의 높이 · 사이드바 폭 · 셸의 `h-screen` 이
// 다 모여야 재현된다. jsdom 에는 레이아웃이 없고, 헤드리스 크롬 하네스
// (`tests/a11y/touchTargets.test.tsx`)는 컴포넌트를 낱개로 그리므로 이 조합을 못 만든다.
// 그래서 여기서는 **그 줄이 높이 하한을 갖는다**는 사실만 잠근다. 다시 `min-h-0` 로 돌아가면
// 빨간불이 난다. 진짜 재현은 실제 스택을 띄운 브라우저 실측이고, 그 결과는 PR 본문에 있다.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";
import defaultTheme from "tailwindcss/defaultTheme";

import { theme } from "../../../../tailwind.config.mjs";

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const SOURCE_PATH = resolve(FRONTEND_ROOT, "components/features/Terminal/TerminalContainer.tsx");
const SOURCE = readFileSync(SOURCE_PATH, "utf8");

/** 사이드바와 패널 칸을 담은 줄 — 이 줄이 접히면 패널 안의 모든 조작부가 못 눌린다. */
const PANEL_ROW = /<div className="([^"]+)">\s*\n\s*<SymbolSidebar \/>/;

/** 그 줄 **안**의 패널 열 — 좁은 폭에서 사이드바 아래로 쌓이므로(#425) 자기 하한을 따로 가져야
 *  한다. 위 형제가 자리를 먹으면 `min-h-0 flex-1` 인 채로는 같은 방식으로 0 이 된다. */
const PANEL_COLUMN = /<SymbolSidebar \/>\s*\n\s*\n?\s*<div className="([^"]+)">/;

/** 격자 한 줄(`auto-rows-[minmax(20rem,1fr)]`)의 높이 — 패널 줄의 하한은 이보다 낮으면 안 된다.
 *  값이 아니라 이 관계가 근거다: 패널 한 칸이 격자 한 줄보다 얇으면 머리만 남고 본문이 사라진다. */
const GRID_ROW_FLOOR_PX = 320;

/** 클래스 목록에서 **구간 접두어가 없는** `min-h-*` 유틸리티를 고른다 — 좁은 폭에서 실제로
 *  걸리는 것이 그것이다(`lg:min-h-0` 은 넓은 폭에서만 산다). 없으면 빈 문자열을 낸다. */
function pickBaseMinHeight(classes: string): string {
  return classes.split(/\s+/).find((utility) => utility.startsWith("min-h-")) ?? "";
}

/** `min-h-*` 유틸리티를 px 로 읽는다 — 못 읽으면 `null`(호출부가 실패로 센다). */
function resolveMinHeightPx(utility: string): number | null {
  const match = /^min-h-(?:\[(.+)\]|(.+))$/.exec(utility);
  if (!match) return null;

  const scales = {
    ...(defaultTheme.spacing as Record<string, string>),
    ...(defaultTheme.minHeight as Record<string, string>),
    ...((theme?.extend?.spacing ?? {}) as Record<string, string>),
    ...((theme?.extend?.minHeight ?? {}) as Record<string, string>),
  };
  const raw = match[1] ?? scales[match[2]];
  if (typeof raw !== "string") return null;

  const value = /^(-?[\d.]+)(px|rem)$/.exec(raw.trim());
  if (!value) return null;
  return Number(value[1]) * (value[2] === "rem" ? 16 : 1);
}

describe("터미널 패널 줄 — 0 으로 접히지 않는다 (#289)", () => {
  it("사이드바를 담은 줄과 그 안의 패널 열을 소스에서 찾는다 — 못 찾으면 실패한다(검사 0건으로 초록이 되지 않게)", () => {
    expect(
      PANEL_ROW.test(SOURCE),
      `${SOURCE_PATH} 에서 «<SymbolSidebar/> 를 담은 flex 줄» 을 못 찾았다 — 구조가 바뀌었으면 이 검사도 같이 옮겨라`,
    ).toBe(true);
    expect(
      PANEL_COLUMN.test(SOURCE),
      `${SOURCE_PATH} 에서 «<SymbolSidebar/> 다음의 패널 열» 을 못 찾았다 — 구조가 바뀌었으면 이 검사도 같이 옮겨라`,
    ).toBe(true);
  });

  // 두 상자 모두 같은 사유로 하한이 필요하다 — 넓은 폭에서는 위 형제가 적재 콘솔이고(#289),
  // 좁은 폭에서는 사이드바가 패널 열 위에 눕는다(#425). 축만 다르고 결함은 같다.
  it.each([
    ["패널 줄", PANEL_ROW],
    ["패널 열", PANEL_COLUMN],
  ])("%s — 높이 하한을 갖는다. `min-h-0` 이면 위 형제가 클 때 0 으로 접힌다", (name, pattern) => {
    const classes = pattern.exec(SOURCE)?.[1] ?? "";
    const sizing = pickBaseMinHeight(classes);
    const px = resolveMinHeightPx(sizing);

    // **문법이 아니라 의미로 잰다.** 종전에는 `/^min-h-\[/` 였는데, 값이 같은 `min-h-80`(=20rem)
    // 으로 바꾸면 옳은 코드인데 빨간불이었다(#289 리뷰). 못 읽는 유틸리티는 실패로 센다 —
    // 「해석 못 했으니 통과」가 되면 그물이 조용히 비는 것이다.
    expect(px, `${name} 의 높이 유틸리티 «${sizing}» 를 px 로 못 읽었다 (클래스: «${classes}»)`).not.toBeNull();
    expect(px, `${name} 의 하한이 ${px}px 이다 — 격자 한 줄(${GRID_ROW_FLOOR_PX}px)보다 낮다`).toBeGreaterThanOrEqual(
      GRID_ROW_FLOOR_PX,
    );
  });
});
