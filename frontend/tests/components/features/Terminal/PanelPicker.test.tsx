// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PanelPicker } from "@/components/features/Terminal/PanelPicker";
import { listPanelDefinitions } from "@/lib/terminal/panelRegistry";
import type { PanelDefinition } from "@/types/terminal/panel";

vi.mock("@/lib/terminal/panelRegistry", () => ({
  listPanelDefinitions: vi.fn(() => []),
}));

afterEach(() => {
  cleanup();
  vi.mocked(listPanelDefinitions).mockReset();
  vi.mocked(listPanelDefinitions).mockReturnValue([]);
});

const CHART_DEFINITION: PanelDefinition = {
  type: "chart",
  title: "차트",
  capability: "candles",
  needsSymbol: true,
  defaultSize: { w: 6, h: 4 },
  minSize: { w: 2, h: 2 },
  load: () => Promise.resolve({ default: () => null }),
};

const ORDERBOOK_DEFINITION: PanelDefinition = {
  type: "orderbook",
  title: "호가",
  capability: "orderbook",
  needsSymbol: true,
  defaultSize: { w: 4, h: 4 },
  minSize: { w: 2, h: 2 },
  load: () => Promise.resolve({ default: () => null }),
};

function setup(definitions: PanelDefinition[] = []) {
  vi.mocked(listPanelDefinitions).mockReturnValue(definitions);
  const onAdd = vi.fn();
  render(<PanelPicker panels={[]} onAdd={onAdd} />);
  const trigger = screen.getByRole("button", { name: "패널 추가" });
  return { trigger, onAdd };
}

describe("PanelPicker — 레지스트리가 빈 상태(T3-2 명세)", () => {
  it("트리거에 포커스한 뒤 Enter 로 열리고 Escape 로 닫힌다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menu")).toBeTruthy();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("Escape 로 닫힌 뒤 포커스가 트리거로 돌아온다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([]);

    trigger.focus();
    await user.keyboard("{Enter}{Escape}");

    expect(document.activeElement).toBe(trigger);
  });

  it("빈 상태 안내 문구를 role=status 로 보여준다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([]);

    trigger.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("status").textContent).toBe("등록된 패널이 없습니다.");
  });
});

describe("PanelPicker — 레지스트리에 항목이 있는 상태(테스트 내부 주입)", () => {
  it("트리거에 포커스한 뒤 Enter 로 열리고 Escape 로 닫히며 포커스가 트리거로 돌아온다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menu")).toBeTruthy();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("열리면 첫 항목에 자동 포커스한다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");

    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "차트" }));
  });

  it("항목을 클릭하면 onAdd 가 호출되고 메뉴가 닫힌다", async () => {
    const user = userEvent.setup();
    const { trigger, onAdd } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    await user.click(screen.getByRole("menuitem", { name: "차트" }));

    expect(onAdd).toHaveBeenCalledWith(CHART_DEFINITION);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("메뉴 바깥 pointerdown 으로 닫힌다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menu")).toBeTruthy();

    fireEvent.pointerDown(document.body);

    expect(screen.queryByRole("menu")).toBeNull();
  });
});

describe("PanelPicker — WAI-ARIA menu 갭 3건 (#314)", () => {
  it("ArrowDown/ArrowUp 으로 항목 사이를 순회한다(갭 2)", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION, ORDERBOOK_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "차트" }));

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "호가" }));

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "차트" })); // 순환

    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "호가" }));
  });

  it("메뉴를 연 채 Tab 으로 나가면 메뉴가 닫힌다(갭 1) — 그 뒤 Escape 를 기다릴 필요가 없다", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menu")).toBeTruthy();

    await user.keyboard("{Tab}");

    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("항목에 포커스가 있는 채로 Tab 으로 나가도 닫힌다(갭 1, 항목이 있는 경우의 실제 재현 경로)", async () => {
    const user = userEvent.setup();
    const { trigger } = setup([CHART_DEFINITION]);

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "차트" }));

    await user.keyboard("{Tab}");

    expect(screen.queryByRole("menu")).toBeNull();
  });
});
