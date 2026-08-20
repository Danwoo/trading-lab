// @vitest-environment jsdom
//
// 화면 결정 §20.2(패널은 보드를 덮지 않는다) · §21.3(에이전트만 620 토글) · §21.6(폭 구간).
//
// **폭은 이제 CSS 가 정한다** — jsdom 은 Tailwind 를 적용하지 않으므로 여기서 잴 수 있는 것은
// 「어느 구간에 어떤 유틸리티가 붙었나」까지다. 실제로 그 폭으로 그려지는지는 브라우저 확인의
// 몫이고, 그 대신 **폭이 JS 로 돌아오지 않았다**는 것(인라인 style 0)은 여기서 막는다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProductPanel } from "@/components/shared/Layout/ProductPanel";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { type RailItem } from "@/constants/shell";

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

/** 부분문자열로 보면 `xl:w-shell-panel` 이 `xl:w-shell-panel-expanded` 안에서도 참이 된다. */
function classesOf(el: HTMLElement): Set<string> {
  return new Set(el.className.split(/\s+/).filter(Boolean));
}

function setup(overrides: { item?: RailItem; expanded?: boolean } = {}) {
  const onClose = vi.fn();
  const onToggleExpanded = vi.fn();
  render(
    <ProductPanel
      id="product-panel"
      item={overrides.item ?? BOT_ITEM}
      expanded={overrides.expanded ?? false}
      onToggleExpanded={onToggleExpanded}
      onClose={onClose}
    />,
  );
  const panel = document.getElementById("product-panel") as HTMLElement;
  return { panel, onClose, onToggleExpanded };
}

describe("ProductPanel — 폭은 CSS 가 정한다 (§21.3 · §21.6)", () => {
  it("폭을 인라인 style 로 쓰지 않는다 — 여기가 다시 채워지면 첫 페인트가 서버·클라이언트에서 갈린다", () => {
    const { panel } = setup();

    expect(panel.style.width).toBe("");
    expect(panel.style.flex).toBe("");
    expect(panel.style.maxWidth).toBe("");
    expect(panel.getAttribute("style")).toBeNull();
  });

  it("기본(1024 미만)은 보드를 덮는다 — 자리를 차지하지 않고 위에 얹힌다", () => {
    const { panel } = setup();
    const classes = classesOf(panel);

    expect(classes.has("absolute")).toBe(true);
    expect(classes.has("inset-0")).toBe(true);
    expect(classes.has("z-20")).toBe(true);
  });

  it("1024 이상에서는 형제로 돌아와 300 을 차지한다", () => {
    const { panel } = setup();
    const classes = classesOf(panel);

    expect(classes.has("lg:static")).toBe(true);
    expect(classes.has("lg:w-shell-panel-compact")).toBe(true);
    // 폭을 줬으면 줄어들지 않아야 한다 — 안 그러면 보드가 밀 때 300 이 지켜지지 않는다.
    expect(classes.has("lg:flex-none")).toBe(true);
  });

  it("1280 이상에서는 372 다", () => {
    const { panel } = setup();
    const classes = classesOf(panel);

    expect(classes.has("xl:w-shell-panel")).toBe(true);
    expect(classes.has("xl:w-shell-panel-expanded")).toBe(false);
  });

  it("에이전트를 넓히면 620 쪽 하나만 실린다 — 둘을 함께 실으면 CSS 순서가 승자를 정한다", () => {
    const { panel } = setup({ item: AGENT_ITEM, expanded: true });
    const classes = classesOf(panel);

    expect(classes.has("xl:w-shell-panel-expanded")).toBe(true);
    expect(classes.has("xl:w-shell-panel")).toBe(false);
  });

  it("넓힌 채로도 1024~1280 의 폭은 300 그대로다 — 620 은 `xl:` 에만 걸려 있다", () => {
    const { panel } = setup({ item: AGENT_ITEM, expanded: true });
    const classes = classesOf(panel);

    expect(classes.has("lg:w-shell-panel-compact")).toBe(true);
    expect([...classes].filter((c) => c.startsWith("lg:w-"))).toEqual(["lg:w-shell-panel-compact"]);
  });
});

describe("ProductPanel — 620 토글은 에이전트에만, 1280 이상에만 (§21.3 · §21.6)", () => {
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

  // §21.6 이 620 을 허용한 것은 1280 이상뿐이다. 그 아래에서 버튼을 보이면 눌러도 폭이 안 바뀌는데
  // `aria-pressed` 만 눌림으로 바뀌어 스크린리더에게 거짓 상태를 알린다. `hidden` 은 `display:none`
  // 이라 접근성 트리에서도 빠진다 — 「보이지만 안 먹는 버튼」이 생길 수 없다.
  //
  // 지키는 것은 「xl 미만에서 숨고 xl 에서 보인다」는 짝이지 특정 유틸리티 이름이 아니다 —
  // 표시 유틸리티는 `xl:block` 에서 `xl:inline-flex` 로 옮겼다(#289: 표적 24×24 를 위해 상자를
  // flex 로 세운다). 그래서 이름 하나가 아니라 「보이게 하는 xl 유틸리티가 있는가」로 본다.
  it("1280 미만에서는 숨는다 — `hidden` + 보이게 하는 xl 유틸리티 두 짝이 다 있어야 한다", () => {
    setup({ item: AGENT_ITEM });
    const classes = classesOf(screen.getByRole("button", { name: /넓히기/ }));

    expect(classes.has("hidden")).toBe(true);
    expect([...classes].filter((c) => /^xl:(block|inline-block|flex|inline-flex|grid)$/.test(c))).toHaveLength(1);
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
