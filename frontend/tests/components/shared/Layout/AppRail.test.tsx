// @vitest-environment jsdom
//
// #73 S2 — 레일이 **키보드만으로** 닿고 토글되는가.
//
// 레일은 폭 46px 라 아이콘만 있다. 접근명이 없으면 스크린리더 사용자에게는 이름 없는 버튼 여덟
// 개가 되고, 포커스가 안 가면 마우스 없는 사용자에게는 화면 전환 수단이 통째로 사라진다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pathname = { current: "/bench" };
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

const { AppRail } = await import("@/components/shared/Layout/AppRail");
const { RAIL_ITEMS, RAIL_FOOTER_ITEMS, RAIL_WIDTH_PX } = await import("@/constants/shell");

const railItems = [...RAIL_ITEMS.filter((item) => item !== null), ...RAIL_FOOTER_ITEMS];

function renderRail(openPanelId: string | null = null) {
  const onTogglePanel = vi.fn();
  render(<AppRail openPanelId={openPanelId} onTogglePanel={onTogglePanel} panelRegionId="product-panel" />);
  return { onTogglePanel };
}

beforeEach(() => {
  pathname.current = "/bench";
});
afterEach(cleanup);

describe("AppRail (#73)", () => {
  it("검사 대상이 있다 — 레일 항목이 0건이면 아래 단언이 전부 무의미하다", () => {
    expect(railItems.length).toBeGreaterThan(5);
  });

  it("모든 항목에 접근명이 붙어 있다", () => {
    renderRail();
    for (const item of railItems) {
      const found = screen.getAllByRole(item.kind === "destination" ? "link" : "button", {
        name: new RegExp(item.label),
      });
      expect(found.length, `${item.label} 에 접근명이 없다`).toBeGreaterThan(0);
    }
  });

  it("46px 폭과 §20.2 의 레일 순서를 지킨다", () => {
    renderRail();
    const rail = screen.getByRole("navigation", { name: "주요 화면" });
    expect(rail.style.width).toBe(`${RAIL_WIDTH_PX}px`);

    // 접근명 순서가 곧 화면 순서다 — 확정된 순서(§20.2 + §22.4)가 흔들리면 여기서 걸린다.
    const names = Array.from(rail.querySelectorAll("a, button")).map((el) => el.getAttribute("aria-label"));
    expect(names[0]).toBe("실험대");
    expect(names[1]).toMatch(/^리서치/);
    expect(names.at(-1)).toBe("설정");
  });

  it("패널 아이콘은 Enter 와 Space 로 토글된다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = renderRail();

    await user.tab(); // 실험대(첫 항목)
    await user.tab(); // 리서치
    await user.tab(); // 봇
    expect(document.activeElement?.getAttribute("aria-label")).toBe("봇");

    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onTogglePanel.mock.calls).toEqual([["bots"], ["bots"]]);
  });

  it("열린 패널은 aria-pressed 와 aria-controls 로 자리와 이어진다", () => {
    renderRail("bots");
    const bots = screen.getByRole("button", { name: "봇" });
    expect(bots.getAttribute("aria-pressed")).toBe("true");
    expect(bots.getAttribute("aria-controls")).toBe("product-panel");

    const trades = screen.getByRole("button", { name: "거래 로그" });
    expect(trades.getAttribute("aria-pressed")).toBe("false");
  });

  it("지금 있는 화면은 aria-current 로 표시된다", () => {
    pathname.current = "/terminal";
    renderRail();
    expect(screen.getByRole("link", { name: "시세" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "실험대" }).getAttribute("aria-current")).toBeNull();
  });

  it("준비 중 항목은 포커스는 받되 눌러도 아무 일도 안 한다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = renderRail();
    const research = screen.getByRole("button", { name: /^리서치/ });

    expect(research.getAttribute("aria-disabled")).toBe("true");
    research.focus();
    expect(document.activeElement).toBe(research);

    await user.keyboard("{Enter}");
    expect(onTogglePanel).not.toHaveBeenCalled();
  });
});
