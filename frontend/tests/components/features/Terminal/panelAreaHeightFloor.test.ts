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

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const SOURCE_PATH = resolve(FRONTEND_ROOT, "components/features/Terminal/TerminalContainer.tsx");
const SOURCE = readFileSync(SOURCE_PATH, "utf8");

/** 사이드바와 패널 칸을 담은 줄 — 이 줄이 접히면 패널 안의 모든 조작부가 못 눌린다. */
const PANEL_ROW = /<div className="flex ([a-z0-9[\]:.\-_]+) flex-1">\s*\n\s*<SymbolSidebar \/>/;

describe("터미널 패널 줄 — 0 으로 접히지 않는다 (#289)", () => {
  it("사이드바를 담은 줄을 소스에서 찾는다 — 못 찾으면 실패한다(검사 0건으로 초록이 되지 않게)", () => {
    expect(
      PANEL_ROW.test(SOURCE),
      `${SOURCE_PATH} 에서 «<SymbolSidebar/> 를 담은 flex 줄» 을 못 찾았다 — 구조가 바뀌었으면 이 검사도 같이 옮겨라`,
    ).toBe(true);
  });

  it("그 줄이 높이 하한을 갖는다 — `min-h-0` 이면 적재 콘솔이 클 때 0 으로 접힌다", () => {
    const sizing = PANEL_ROW.exec(SOURCE)?.[1] ?? "";

    expect(sizing, `패널 줄의 높이 유틸리티가 «${sizing}» 다`).toMatch(/^min-h-\[/);
    expect(sizing).not.toBe("min-h-0");
  });
});
