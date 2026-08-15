// @vitest-environment jsdom
//
// 보드 쪽 두 규칙 — §20.2 셋째 줄(패널에서 고르면 보드가 그 지점을 표시) · §21.6(1280 미만에서
// 격자·곡선은 탭으로 하나씩).
//
// **보드는 이제 폭을 JS 로 읽지 않는다.** 두 벌(나란히 / 탭)을 다 그려 두고 `xl:` 이 한 벌을
// `display:none` 으로 끈다 — jsdom 은 Tailwind 를 적용하지 않으므로 여기서는 두 벌이 다 보인다.
// 그래서 이 파일이 지키는 것은 ㉠ 두 벌이 각자 맞는 구간 클래스를 달고 있다 ㉡ 탭 상호작용이
// 살아 있다 ㉢ **`matchMedia` 없이도 그려진다**(폭 판단이 JS 로 돌아오면 여기서 깨진다) 셋이다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BenchPage from "@/app/(main)/bench/page";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";

beforeEach(() => {
  useBenchSelectionStore.setState({ selection: null });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** 1280 미만용 탭 벌 — 탭 목록을 담고 있는 상자. */
function tabbedBoard(): HTMLElement {
  return screen.getByRole("tablist", { name: "보드 보기" }).parentElement as HTMLElement;
}

/** 1280 이상용 나란히 벌 — 곡선은 기본 탭(격자)에서 이쪽에만 있으므로 이것으로 집는다. */
function sideBySideBoard(): HTMLElement {
  return screen.getByRole("region", { name: "곡선" }).parentElement as HTMLElement;
}

describe("실험대 보드 — 폭을 CSS 가 가른다 (§21.6)", () => {
  it("`matchMedia` 가 없어도 보드가 그려진다 — 폭 판단이 JS 로 돌아오면 여기서 깨진다", () => {
    vi.stubGlobal("matchMedia", undefined);

    expect(() => render(<BenchPage />)).not.toThrow();
    expect(screen.getByRole("tablist", { name: "보드 보기" })).toBeTruthy();
  });

  it("나란히 벌은 1280 이상에만 산다 — 기본은 꺼져 있고 `xl:` 에서 격자 2열이 된다", () => {
    render(<BenchPage />);
    const classes = new Set(sideBySideBoard().className.split(/\s+/));

    expect(classes.has("hidden")).toBe(true);
    expect(classes.has("xl:grid")).toBe(true);
    expect(classes.has("xl:grid-cols-2")).toBe(true);
  });

  it("탭 벌은 1280 미만에만 산다", () => {
    render(<BenchPage />);

    expect(new Set(tabbedBoard().className.split(/\s+/)).has("xl:hidden")).toBe(true);
  });

  it("나란히 벌에는 격자와 곡선이 함께 있다", () => {
    render(<BenchPage />);
    const board = within(sideBySideBoard());

    expect(board.getByRole("region", { name: "격자" })).toBeTruthy();
    expect(board.getByRole("region", { name: "곡선" })).toBeTruthy();
  });

  it("탭 벌은 한 번에 하나만 내놓는다 — 기본은 격자이고 곡선은 그 안에 없다", () => {
    render(<BenchPage />);
    const board = within(tabbedBoard());

    expect(board.getByRole("region", { name: "격자" })).toBeTruthy();
    expect(board.queryByRole("region", { name: "곡선" })).toBeNull();
  });

  it("탭은 화살표 키로 옮겨진다", async () => {
    const user = userEvent.setup();
    render(<BenchPage />);

    screen.getByRole("tab", { name: "격자" }).focus();
    await user.keyboard("{ArrowRight}");

    const board = within(tabbedBoard());
    expect(screen.getByRole("tab", { name: "곡선" }).getAttribute("aria-selected")).toBe("true");
    expect(board.getByRole("region", { name: "곡선" })).toBeTruthy();
    expect(board.queryByRole("region", { name: "격자" })).toBeNull();
  });

  it("내 봇·오늘 할 일은 어느 폭에서도 접지 않는다", () => {
    render(<BenchPage />);

    expect(screen.getByRole("region", { name: "내 봇" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "오늘 할 일" })).toBeTruthy();
  });
});

describe("실험대 보드 — 패널에서 고르면 보드가 그 지점을 표시한다 (§20.2 셋째 줄)", () => {
  it("선택이 없으면 어느 자리도 표시되지 않는다", () => {
    render(<BenchPage />);

    expect(screen.queryByText(/여기 표시합니다/)).toBeNull();
  });

  it("패널에서 고른 격자 지점은 「격자」 자리에 뜬다 — 두 벌 다 같은 것을 말해야 한다", () => {
    useBenchSelectionStore.setState({
      selection: { kind: "grid-point", id: "g-42", label: "칸 42", origin: "panel" },
    });
    render(<BenchPage />);

    const grids = screen.getAllByRole("region", { name: "격자" });
    expect(grids.length).toBeGreaterThan(0);
    for (const grid of grids) {
      expect(grid.textContent).toContain("칸 42");
      expect(grid.textContent).toContain("패널에서 고른 지점을 여기 표시합니다");
    }
  });

  it("종류가 다르면 다른 자리가 받는다 — 봇 선택은 「내 봇」이 받고 「격자」는 조용하다", () => {
    useBenchSelectionStore.setState({
      selection: { kind: "bot", id: "bot-1", label: "봇 알파", origin: "panel" },
    });
    render(<BenchPage />);

    expect(screen.getByRole("region", { name: "내 봇" }).textContent).toContain("봇 알파");
    for (const grid of screen.getAllByRole("region", { name: "격자" })) {
      expect(grid.textContent).not.toContain("봇 알파");
    }
  });
});
