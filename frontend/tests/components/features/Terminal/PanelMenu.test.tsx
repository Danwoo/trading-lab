// @vitest-environment jsdom
//
// 이슈 #314 갭 3 — WAI-ARIA menu button 패턴은 트리거에서 ArrowDown 으로도 메뉴를 열고 첫
// 항목에 포커스를 줘야 한다. 지금까지는 Enter/Space(버튼 기본 활성화)만 열었다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PanelMenu } from "@/components/features/Terminal/PanelMenu";

afterEach(() => cleanup());

function setup() {
  return render(<PanelMenu collapsed={false} onToggleCollapse={vi.fn()} onClose={vi.fn()} />);
}

describe("PanelMenu — 트리거 ArrowDown 오픈 (#314 갭 3)", () => {
  it("트리거에 포커스한 뒤 ArrowDown 을 누르면 메뉴가 열리고 첫 항목에 포커스한다", async () => {
    const user = userEvent.setup();
    setup();

    const trigger = screen.getByRole("button", { name: "패널 메뉴" });
    trigger.focus();
    expect(screen.queryByRole("menu")).toBeNull();

    await user.keyboard("{ArrowDown}");

    expect(screen.getByRole("menu")).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "접기" }));
  });

  it("Enter/Space 로 여는 기존 경로는 그대로 동작한다 — 회귀 없음", async () => {
    const user = userEvent.setup();
    setup();

    const trigger = screen.getByRole("button", { name: "패널 메뉴" });
    trigger.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("menu")).toBeTruthy();
  });
});
