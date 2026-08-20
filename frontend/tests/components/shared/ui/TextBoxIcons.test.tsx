// @vitest-environment jsdom
//
// `TextBox` 의 클리어·토글 아이콘은 컴포넌트 **안**에서 색이 정해진다 — 호출부의 `className` 은
// `<input>` 에만 내려가므로 밖에서 못 덮는다. 그래서 그 색은 **어두운 셸과 라이트 `/admin`
// 양쪽에서** 읽혀야 한다. 종전 `hover:text-gray-600/700` 은 밝은 바탕 전제라 어두운 셸에서
// 대비가 1.57:1 로 떨어져 **마우스를 올리면 아이콘이 사라졌다**.
//
// **이 파일이 지키는 규칙이 한 번 뒤집혔다.** 종전에는 토큰(`text-ink-*`)도 금지였다 — `/admin`
// 셸이 `data-theme="light"` 를 선언하지 않아 토큰이 거기서도 다크로 풀렸기 때문이다. 그래서
// 원시 색을 박았고, 그 프리미티브가 다크 보드에서 재사용되자 이번엔 **흰 상자**가 됐다(실측
// 2.54:1). 셸이 선언하게 고쳤으므로 이제 **토큰이 정답이고 원시 색이 금지**다.
//
// jsdom 은 대비를 못 잰다(실제 값은 브라우저 실측이 정본). 여기서 막는 것은 **되돌아옴**이다 —
// 테마를 박은 색이 다시 들어오는 것, 그리고 `autoComplete` 통로가 사라지는 것.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { TextBox } from "@/components/shared/ui/TextBox";

/** 테마를 박은 색 — 이것이 아이콘에 들어오면 반대 테마에서 안 보인다. */
const THEME_BOUND = [
  /text-gray-\d{2,3}/, // 원시 팔레트 — 어느 쪽을 고르든 반대편이 죽는다
  /text-(?:slate|zinc|neutral|stone)-\d{2,3}/,
  /text-white/,
  /text-black/,
  /text-current/, // 이 래퍼에는 잉크가 없어 브라우저 기본색(검정)으로 떨어진다
];

function iconButton(name: RegExp): HTMLElement {
  return screen.getByRole("button", { name });
}

describe("TextBox 아이콘 — 양쪽 테마에서 읽히는 색만 쓴다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("비밀번호 토글이 테마를 박은 색을 쓰지 않는다", () => {
    render(<TextBox name="password" mode="password" showPasswordToggle defaultValue="x" />);

    const cls = iconButton(/비밀번호/).className;
    for (const pattern of THEME_BOUND) {
      expect(cls, `${pattern} 가 들어왔다: ${cls}`).not.toMatch(pattern);
    }
  });

  it("잉크를 **토큰으로** 준다 — 셸이 선언한 테마를 따라간다", () => {
    render(<TextBox name="password" mode="password" showPasswordToggle defaultValue="x" />);

    // 색을 아예 안 주면 브라우저 기본색(검정)으로 떨어져 어두운 셸에서 사라진다.
    expect(iconButton(/비밀번호/).className).toMatch(/text-ink(-|\s|$)/);
  });

  it("hover 는 글자색이 아니라 바탕으로 준다 — 한 색으로 양쪽을 다 올릴 수 없다", () => {
    render(<TextBox name="password" mode="password" showPasswordToggle defaultValue="x" />);

    const cls = iconButton(/비밀번호/).className;
    expect(cls).toMatch(/hover:bg-/);
    expect(cls, `hover 가 글자색을 바꾼다: ${cls}`).not.toMatch(/hover:text-/);
  });

  it("키보드 사용자도 같은 표식을 받는다", () => {
    render(<TextBox name="password" mode="password" showPasswordToggle defaultValue="x" />);

    expect(iconButton(/비밀번호/).className).toMatch(/focus-visible:/);
  });

  it("autoComplete 통로가 있다 — 호출부만으로는 못 닫힌다 (WCAG 1.3.5)", () => {
    render(<TextBox name="email" mode="email" autoComplete="username" defaultValue="" />);

    expect(screen.getByRole("textbox").getAttribute("autocomplete")).toBe("username");
  });
});
