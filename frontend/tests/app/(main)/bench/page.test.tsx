// @vitest-environment jsdom
//
// 보드 쪽 두 규칙 — §20.2 셋째 줄(패널에서 고르면 보드가 그 지점을 표시) · §21.6(1280 미만에서
// 격자·곡선은 탭으로 하나씩). jsdom 에는 `matchMedia` 가 없어 폭 구간을 직접 세워 준다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BenchPage from "@/app/(main)/bench/page";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { VIEWPORT_COMPACT_MIN_PX, VIEWPORT_WIDE_MIN_PX } from "@/constants/shell";

/** 주어진 뷰포트 폭으로 `matchMedia` 를 세운다 — `(min-width: Npx)` 만 해석하면 충분하다. */
function stubViewportWidth(widthPx: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const min = Number(/\(min-width:\s*(\d+)px\)/.exec(query)?.[1] ?? 0);
    return {
      matches: widthPx >= min,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    } as unknown as MediaQueryList;
  });
}

beforeEach(() => {
  useBenchSelectionStore.setState({ selection: null });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("실험대 보드 — 패널에서 고르면 보드가 그 지점을 표시한다 (§20.2 셋째 줄)", () => {
  it("선택이 없으면 어느 자리도 표시되지 않는다", () => {
    stubViewportWidth(VIEWPORT_WIDE_MIN_PX);
    render(<BenchPage />);

    expect(screen.queryByText(/여기 표시합니다/)).toBeNull();
  });

  it("패널에서 고른 격자 지점은 「격자」 자리에 뜬다", () => {
    stubViewportWidth(VIEWPORT_WIDE_MIN_PX);
    useBenchSelectionStore.setState({
      selection: { kind: "grid-point", id: "g-42", label: "칸 42", origin: "panel" },
    });
    render(<BenchPage />);

    const grid = screen.getByRole("region", { name: "격자" });
    expect(grid.textContent).toContain("칸 42");
    expect(grid.textContent).toContain("패널에서 고른 지점을 여기 표시합니다");
  });

  it("종류가 다르면 다른 자리가 받는다 — 봇 선택은 「내 봇」이 받고 「격자」는 조용하다", () => {
    stubViewportWidth(VIEWPORT_WIDE_MIN_PX);
    useBenchSelectionStore.setState({
      selection: { kind: "bot", id: "bot-1", label: "봇 알파", origin: "panel" },
    });
    render(<BenchPage />);

    expect(screen.getByRole("region", { name: "내 봇" }).textContent).toContain("봇 알파");
    expect(screen.getByRole("region", { name: "격자" }).textContent).not.toContain("봇 알파");
  });
});

describe("실험대 보드 — 좁은 화면에서는 보드가 먼저 양보한다 (§21.6)", () => {
  it("1280 이상이면 격자와 곡선이 나란히 있다", () => {
    stubViewportWidth(VIEWPORT_WIDE_MIN_PX);
    render(<BenchPage />);

    expect(screen.getByRole("region", { name: "격자" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "곡선" })).toBeTruthy();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("1280 미만이면 탭이 되어 하나씩만 보인다", () => {
    stubViewportWidth(VIEWPORT_COMPACT_MIN_PX);
    render(<BenchPage />);

    expect(screen.getByRole("tablist", { name: "보드 보기" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "격자" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "곡선" })).toBeNull();
  });

  it("탭은 화살표 키로 옮겨진다", async () => {
    const user = userEvent.setup();
    stubViewportWidth(VIEWPORT_COMPACT_MIN_PX);
    render(<BenchPage />);

    screen.getByRole("tab", { name: "격자" }).focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "곡선" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("region", { name: "곡선" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "격자" })).toBeNull();
  });

  it("1024 미만도 같은 탭이다 — 그 구간에서 달라지는 것은 패널이 보드를 덮는다는 것뿐", () => {
    stubViewportWidth(VIEWPORT_COMPACT_MIN_PX - 1);
    render(<BenchPage />);

    expect(screen.getByRole("tablist", { name: "보드 보기" })).toBeTruthy();
  });

  it("내 봇·오늘 할 일은 어느 폭에서도 접지 않는다", () => {
    stubViewportWidth(VIEWPORT_COMPACT_MIN_PX - 1);
    render(<BenchPage />);

    expect(screen.getByRole("region", { name: "내 봇" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "오늘 할 일" })).toBeTruthy();
  });
});
