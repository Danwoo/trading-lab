// @vitest-environment jsdom
//
// `TextBox` 의 클리어·토글 아이콘은 컴포넌트 **안**에서 색이 정해진다 — 호출부의 `className` 은
// `<input>` 에만 내려가므로 밖에서 못 덮는다. 그래서 그 색은 **어두운 셸과 흰 `/admin` 양쪽에서**
// 읽혀야 한다. 종전 `hover:text-gray-600/700` 은 밝은 바탕 전제라 어두운 셸에서 대비가
// 1.57:1 로 떨어져 **마우스를 올리면 아이콘이 사라졌다**.
//
// jsdom 은 대비를 못 잰다(실제 값은 브라우저 실측이 정본). 여기서 막는 것은 **되돌아옴**이다 —
// 한쪽 테마만 보는 색이 다시 들어오는 것, 그리고 `autoComplete` 통로가 사라지는 것.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { TextBox } from "@/components/shared/ui/TextBox";

/** 한쪽 테마 전제 색 — 이것이 아이콘에 다시 들어오면 반대 테마에서 안 보인다. */
const THEME_BOUND = [
  /text-gray-[6-9]00/, // 밝은 바탕 전제 (어두운 셸에서 사라진다)
  /text-gray-[1-3]00/, // 어두운 바탕 전제 (흰 admin 에서 사라진다)
  /text-ink/, // 토큰 — `:root` 가 다크 기본이라 흰 `/admin` 에서 뒤집힌다
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

  it("비밀번호 토글이 한쪽 테마 전제 색을 쓰지 않는다", () => {
    render(<TextBox name="password" mode="password" showPasswordToggle defaultValue="x" />);

    const cls = iconButton(/비밀번호/).className;
    for (const pattern of THEME_BOUND) {
      expect(cls, `${pattern} 가 들어왔다: ${cls}`).not.toMatch(pattern);
    }
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
