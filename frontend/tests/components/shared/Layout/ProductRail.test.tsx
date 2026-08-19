// @vitest-environment jsdom
//
// 화면 결정 §20.2 「이동 규칙」 **첫째 줄** — 레일 아이콘은 그 패널을 여닫을 뿐 **보드는 안
// 바뀐다.** 코드에서 그것은 「라우팅이 일어나지 않는다」와 같은 말이라, 여기서는 패널 항목이
// `router.push` 를 부르지 않는 것으로 본다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProductRail } from "@/components/shared/Layout/ProductRail";
import { RAIL_ITEMS } from "@/constants/shell";

const push = vi.fn();
let pathname = "/bench";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push }),
}));

const showToast = vi.fn();
vi.mock("@/components/shared/Feedback", () => ({
  showToast: (...args: unknown[]) => showToast(...args),
}));

afterEach(() => {
  cleanup();
  push.mockClear();
  showToast.mockClear();
  pathname = "/bench";
});

function setup(openPanelId: string | null = null) {
  const onTogglePanel = vi.fn();
  render(<ProductRail openPanelId={openPanelId} onTogglePanel={onTogglePanel} panelRegionId="product-panel" />);
  return { onTogglePanel };
}

describe("ProductRail — 레일 아이콘 = 패널 토글 (§20.2 첫째 줄)", () => {
  it("패널 항목을 누르면 토글만 올라가고 화면은 바뀌지 않는다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = setup();

    await user.click(screen.getByRole("button", { name: "봇" }));

    expect(onTogglePanel).toHaveBeenCalledWith("bot");
    expect(push).not.toHaveBeenCalled();
  });

  it("같은 항목을 다시 눌러도 화면은 그대로다 — 닫는 판단은 호출자 몫이라 같은 id 가 다시 올라간다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = setup("bot");

    await user.click(screen.getByRole("button", { name: "봇" }));

    expect(onTogglePanel).toHaveBeenCalledWith("bot");
    expect(push).not.toHaveBeenCalled();
  });

  it("열린 패널 항목은 aria-expanded 와 aria-controls 로 패널 영역을 가리킨다", () => {
    setup("bot");

    const button = screen.getByRole("button", { name: "봇" });
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(button.getAttribute("aria-controls")).toBe("product-panel");
  });

  it("화면 전환 항목(시세)은 반대로 라우팅하고 패널 토글을 부르지 않는다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = setup();

    await user.click(screen.getByRole("button", { name: "시세" }));

    expect(push).toHaveBeenCalledWith("/terminal");
    expect(onTogglePanel).not.toHaveBeenCalled();
  });

  it("레일의 패널 항목 전부가 이 규칙을 지킨다 — 목록이 비면 통과가 아니라 실패다", async () => {
    const user = userEvent.setup();
    const { onTogglePanel } = setup();
    const panelItems = RAIL_ITEMS.filter((item) => item.kind === "panel");

    expect(panelItems.length).toBeGreaterThan(0);
    for (const item of panelItems) {
      await user.click(screen.getByRole("button", { name: item.label }));
    }

    expect(onTogglePanel).toHaveBeenCalledTimes(panelItems.length);
    expect(push).not.toHaveBeenCalled();
  });
});

describe("ProductRail — 에이전트 자리 (§21.3)", () => {
  it("에이전트는 레일의 패널 항목이고, 620 토글을 갖는 유일한 항목이다", () => {
    const expandable = RAIL_ITEMS.filter((item) => item.expandable);

    expect(expandable.map((item) => item.id)).toEqual(["agent"]);
    expect(expandable[0].kind).toBe("panel");
  });
});

describe("ProductRail — 패널을 닫으면 포커스가 레일 버튼으로 돌아온다", () => {
  it("focusItemId 를 받으면 그 버튼에 포커스하고 처리했음을 알린다", () => {
    const onFocusHandled = vi.fn();
    render(
      <ProductRail
        openPanelId={null}
        onTogglePanel={vi.fn()}
        panelRegionId="product-panel"
        focusItemId="bot"
        onFocusHandled={onFocusHandled}
      />,
    );

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "봇" }));
    expect(onFocusHandled).toHaveBeenCalledOnce();
  });
});

// #228 — **미완 레일은 눌러보기 전에 드러난다.**
//
// 아이콘이 9개 보이면 9개가 된다고 읽는다. 눌러서 「아직 없습니다」가 나오기를 몇 번 겪으면
// 레일을 아예 안 누르게 되고, 되는 것까지 안 눌러보게 된다.
//
// 종전 판정(`!isPanel && !item.path`)은 라우트만 봐서, 패널로 열리지만 안이 빈 넷을 놓쳤다 —
// 실측으로 미완 5개 중 1개만 표식이 있었다.
describe("ProductRail — 미완은 눌러보기 전에 드러난다 (#228)", () => {
  function renderRail() {
    return render(<ProductRail openPanelId={null} onTogglePanel={vi.fn()} panelRegionId="product-panel" />);
  }

  it("pending 을 선언한 레일은 전부 표식을 단다 — 패널이든 라우트든", () => {
    const { container } = renderRail();
    const pendingLabels = RAIL_ITEMS.filter((item) => item.pending).map((item) => item.label);

    expect(pendingLabels.length).toBeGreaterThan(0);
    for (const label of pendingLabels) {
      const button = screen.getByRole("button", { name: label });
      expect(button.querySelector("span[aria-hidden]"), `${label} 에 표식이 없다`).not.toBeNull();
    }
    expect(container.querySelectorAll("span[aria-hidden]")).toHaveLength(pendingLabels.length);
  });

  it("되는 레일에는 표식을 달지 않는다", () => {
    renderRail();

    for (const item of RAIL_ITEMS.filter((i) => !i.pending)) {
      const button = screen.getByRole("button", { name: item.label });
      expect(button.querySelector("span[aria-hidden]"), `${item.label} 에 표식이 붙었다`).toBeNull();
    }
  });

  it("열리는 패널을 못 쓴다고 말하지 않는다 — aria-disabled 는 갈 곳이 없을 때만", () => {
    renderRail();

    // 「거래 로그」는 미완이지만 누르면 패널이 열린다 — 못 쓴다고 하면 거짓이다.
    expect(screen.getByRole("button", { name: "거래 로그" }).getAttribute("aria-disabled")).toBeNull();
    // 「리서치」는 경로가 없어 안내만 뜬다.
    expect(screen.getByRole("button", { name: "리서치" }).getAttribute("aria-disabled")).toBe("true");
  });

  it("모든 미완 문구가 언제 오는지 말한다", () => {
    for (const item of RAIL_ITEMS.filter((i) => i.pending)) {
      expect(item.pending, `${item.label} 이 언제 오는지 안 적혔다`).toMatch(/옵니다/);
    }
  });
});

// #229 — **누른 버튼이 이동 중임을 말한다.**
//
// 이동은 즉시 끝나지 않고 그동안 화면은 이전 자리 그대로다. 반응이 없으면 「눌리긴 한 건가」를
// 알 수 없고, 이슈의 관측처럼 「엉뚱한 내용이 그 자리에 있다」로 읽히기도 한다.
//
// 전체 화면 로딩(`loading.tsx`) 대신 누른 버튼만 표시한다 — 빠른 이동에서 화면 전체가 한 번
// 깜빡이는 것이 더 나쁘다.
describe("ProductRail — 이동 중임이 보인다 (#229)", () => {
  function renderRail() {
    return render(<ProductRail openPanelId={null} onTogglePanel={vi.fn()} panelRegionId="product-panel" />);
  }

  it("라우트 레일을 누르면 그 버튼이 바쁜 상태가 된다", async () => {
    const user = userEvent.setup();
    renderRail();

    const button = screen.getByRole("button", { name: "시세" });
    await user.click(button);

    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(push).toHaveBeenCalledOnce();
  });

  it("패널 레일은 이동이 아니라 바쁜 상태가 되지 않는다", async () => {
    const user = userEvent.setup();
    renderRail();

    const button = screen.getByRole("button", { name: "봇" });
    await user.click(button);

    expect(button.getAttribute("aria-busy")).toBeNull();
    expect(push).not.toHaveBeenCalled();
  });

  it("갈 곳이 없는 레일도 바쁜 상태가 되지 않는다 — 안내만 뜬다", async () => {
    const user = userEvent.setup();
    renderRail();

    const button = screen.getByRole("button", { name: "리서치" });
    await user.click(button);

    expect(button.getAttribute("aria-busy")).toBeNull();
    expect(showToast).toHaveBeenCalledOnce();
  });
});
