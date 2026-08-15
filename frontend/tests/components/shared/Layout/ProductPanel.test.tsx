// @vitest-environment jsdom
//
// 화면 결정 §20.2(패널은 보드를 덮지 않는다) · §21.3(에이전트만 620 토글) · §21.6(폭 구간).
// 폭은 「보기 좋은 숫자」가 아니라 결정 문서가 못박은 값이라 수치로 단언한다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProductPanel } from "@/components/shared/Layout/ProductPanel";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { PANEL_COMPACT_WIDTH_PX, PANEL_EXPANDED_WIDTH_PX, PANEL_WIDTH_PX, type RailItem } from "@/constants/shell";
import type { ViewportBand } from "@/hooks/shared/useViewportBand";

const BOT_ITEM: RailItem = {
  id: "bot",
  label: "봇",
  icon: "box",
  kind: "panel",
  pending: "봇 패널 내용은 아직 없습니다.",
};

const AGENT_ITEM: RailItem = { ...BOT_ITEM, id: "agent", label: "에이전트", expandable: true };

beforeEach(() => {
  useBenchSelectionStore.setState({ selection: null });
});

afterEach(() => cleanup());

function setup(overrides: { item?: RailItem; band?: ViewportBand; expanded?: boolean } = {}) {
  const onClose = vi.fn();
  const onToggleExpanded = vi.fn();
  render(
    <ProductPanel
      id="product-panel"
      item={overrides.item ?? BOT_ITEM}
      band={overrides.band ?? "wide"}
      expanded={overrides.expanded ?? false}
      onToggleExpanded={onToggleExpanded}
      onClose={onClose}
    />,
  );
  const panel = document.getElementById("product-panel") as HTMLElement;
  return { panel, onClose, onToggleExpanded };
}

describe("ProductPanel — 폭 (§21.3 · §21.6)", () => {
  it("1280 이상에서는 372px 로 자리를 차지한다 — 덮지 않고 옆으로 민다", () => {
    const { panel } = setup({ band: "wide" });

    expect(panel.style.flex).toBe(`0 0 ${PANEL_WIDTH_PX}px`);
    expect(PANEL_WIDTH_PX).toBe(372);
    expect(panel.className).not.toContain("absolute");
  });

  it("에이전트를 넓히면 620px 이다", () => {
    const { panel } = setup({ item: AGENT_ITEM, band: "wide", expanded: true });

    expect(panel.style.flex).toBe(`0 0 ${PANEL_EXPANDED_WIDTH_PX}px`);
    expect(PANEL_EXPANDED_WIDTH_PX).toBe(620);
  });

  it("1024~1280 에서는 300px 로 줄어든다", () => {
    const { panel } = setup({ band: "compact" });

    expect(panel.style.flex).toBe(`0 0 ${PANEL_COMPACT_WIDTH_PX}px`);
    expect(PANEL_COMPACT_WIDTH_PX).toBe(300);
  });

  it("1024 미만에서만 보드를 덮는다 — 폭을 차지하지 않고 위에 얹힌다", () => {
    const { panel } = setup({ band: "overlay" });

    expect(panel.style.flex).toBe("");
    expect(panel.className).toContain("absolute");
  });
});

describe("ProductPanel — 620 토글은 에이전트에만 있다 (§21.3)", () => {
  it("에이전트 패널에는 넓히기 버튼이 있고 누르면 호출자에게 올라간다", async () => {
    const user = userEvent.setup();
    const { onToggleExpanded } = setup({ item: AGENT_ITEM });

    await user.click(screen.getByRole("button", { name: "에이전트 패널 넓히기" }));

    expect(onToggleExpanded).toHaveBeenCalledOnce();
  });

  it("에이전트가 아닌 패널에는 넓히기 버튼이 아예 없다", () => {
    setup({ item: BOT_ITEM });

    expect(screen.queryByRole("button", { name: /넓히기/ })).toBeNull();
  });

  it("덮는 폭(1024 미만)에서는 에이전트도 넓히기를 내지 않는다 — 이미 전부를 덮고 있다", () => {
    setup({ item: AGENT_ITEM, band: "overlay" });

    expect(screen.queryByRole("button", { name: /넓히기/ })).toBeNull();
  });

  // §21.6 이 620 을 허용한 것은 1280 이상뿐이다. 이 구간에서 버튼을 내면 눌러도 폭이 안 바뀌는데
  // `aria-pressed` 만 눌림으로 바뀌어 스크린리더에게 거짓 상태를 알린다.
  it("1024~1280 에서도 에이전트에게 넓히기를 내지 않는다 — 그 구간의 폭은 300 하나뿐이다", () => {
    setup({ item: AGENT_ITEM, band: "compact" });

    expect(screen.queryByRole("button", { name: /넓히기/ })).toBeNull();
  });

  it("expanded 가 켜진 채 1024~1280 으로 좁아져도 폭은 300 이다 — 상태가 폭을 앞지르지 않는다", () => {
    const { panel } = setup({ item: AGENT_ITEM, band: "compact", expanded: true });

    expect(panel.style.flex).toBe(`0 0 ${PANEL_COMPACT_WIDTH_PX}px`);
  });
});

describe("ProductPanel — 키보드", () => {
  it("열리면 패널로 포커스가 들어간다", () => {
    const { panel } = setup();

    expect(document.activeElement).toBe(panel);
  });

  it("Escape 로 닫힌다", async () => {
    const user = userEvent.setup();
    const { onClose } = setup();

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("닫기 버튼에는 어느 패널인지가 이름에 들어 있다", () => {
    setup();

    expect(screen.getByRole("button", { name: "봇 패널 닫기" })).toBeTruthy();
  });
});

describe("ProductPanel — 보드에서 고르면 내용이 좁혀진다 (§20.2 둘째 줄)", () => {
  it("보드 선택이 있으면 무엇으로 좁혀졌는지 적고 「전체 보기」로 되돌릴 수 있다", async () => {
    const user = userEvent.setup();
    setup();
    useBenchSelectionStore.getState().select({ kind: "bot", id: "bot-1", label: "봇 알파", origin: "board" });

    expect(await screen.findByText("봇 알파")).toBeTruthy();
    expect(screen.getByText(/좁혀져 있습니다/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "전체 보기" }));

    expect(useBenchSelectionStore.getState().selection).toBeNull();
    expect(screen.queryByText(/좁혀져 있습니다/)).toBeNull();
  });

  it("패널에서 고른 것은 「좁혀짐」이 아니라 「보드가 표시 중」으로 적는다 — 방향이 반대다", () => {
    useBenchSelectionStore.setState({
      selection: { kind: "grid-point", id: "g-1", label: "칸 42", origin: "panel" },
    });
    setup();

    expect(screen.getByText(/보드가 표시하고 있습니다/)).toBeTruthy();
    expect(screen.queryByText(/좁혀져 있습니다/)).toBeNull();
  });

  it("선택이 없으면 그 줄 자체가 없다", () => {
    setup();

    expect(screen.queryByRole("button", { name: "전체 보기" })).toBeNull();
  });
});
