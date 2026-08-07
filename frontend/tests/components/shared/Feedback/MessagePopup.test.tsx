// @vitest-environment jsdom
//
// #394 회귀 그물 — `MessagePopup` 이 닫힐 때 `<Popup>` 서브트리를 **언마운트하지 않는다**.
//
// 종전 구현은 `if (!currentMessage) return null` 이었고, `messageStore.resolveMessage` 가
// 확인/취소 즉시 `currentMessage` 를 `null` 로 비우므로 React 가 그 자리에서 서브트리를 뽑았다.
// Radix `Presence` 는 자기 노드의 CSS 애니메이션이 끝날 때까지 언마운트를 늦추는 방식이라,
// 소비자가 먼저 트리를 뽑으면 개입할 기회 자체가 없다(`ui/primitives/dialog.tsx` 불변식 (3)).
//
// **이 파일이 증명하는 것과 못 하는 것 (경계)**
// - 증명한다: 닫힐 때 소비자가 `Popup` 을 마운트한 채 `visible=false` 로만 넘긴다는 계약,
//   그리고 닫히는 동안 마지막 메시지 내용이 그대로 남는다는 것(`displayed` 캐시).
// - 증명하지 못한다: 애니메이션이 실제로 재생되는지. jsdom 에는 레이아웃도 CSS 애니메이션도
//   없어 `Presence` 가 언제나 즉시 언마운트한다 — 그 축은 실브라우저에서만 관측된다
//   (#394 본문의 Playwright rAF 샘플링, `dialogPrimitive.test.tsx` 헤더와 같은 경계).
//   그래서 여기서는 `ui/Popup` 을 스텁으로 갈아끼워 **소비자가 primitive 에 무엇을 넘기는지**를
//   본다 — jsdom 에서 관측 가능한 것은 그것뿐이고, #394 의 결함도 정확히 그 층에 있었다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MessagePopup } from "@/components/shared/Feedback/MessagePopup";
import { MESSAGE_CLOSE_ANIMATION_MS, showMessage, useMessageStore } from "@/stores/shared/messageStore";

// 실제 Radix Popup 대신 스텁 — `visible` 을 DOM 속성으로 노출해 "언마운트 vs 닫힘"을 구분한다.
// 진짜 Popup 은 `visible=false` 면 아무것도 렌더하지 않으므로(Radix Portal 언마운트) 두 상태가
// DOM 에서 구별되지 않는다. 그 구별이 이 파일의 검사 대상이라 여기만 스텁을 쓴다.
vi.mock("@/components/shared/ui/Popup", () => ({
  Popup: ({ visible, title, children }: { visible: boolean; title?: string; children?: React.ReactNode }) => (
    <div data-testid="popup" data-visible={String(visible)}>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}));

beforeEach(() => {
  useMessageStore.setState({ messages: [], currentMessage: null });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  useMessageStore.setState({ messages: [], currentMessage: null });
});

describe("MessagePopup — 닫힘 시 언마운트 금지 (#394)", () => {
  it("메시지가 한 번도 안 뜬 상태에서는 아무것도 렌더하지 않는다", () => {
    render(<MessagePopup />);
    expect(screen.queryByTestId("popup")).toBeNull();
  });

  it("확인을 눌러 currentMessage 가 비어도 Popup 은 마운트된 채 visible=false 로만 바뀐다", async () => {
    const user = userEvent.setup();
    render(<MessagePopup />);

    act(() => {
      void showMessage("삭제 확인", "정말 삭제할까요?", { type: "confirm" });
    });

    const popup = await screen.findByTestId("popup");
    expect(popup.getAttribute("data-visible")).toBe("true");
    expect(screen.getByText("삭제 확인")).toBeTruthy();
    expect(screen.getByText("정말 삭제할까요?")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "확인" }));

    // 스토어는 즉시 비워진다 — 그래도 서브트리는 살아 있어야 한다.
    await waitFor(() => expect(useMessageStore.getState().currentMessage).toBeNull());
    const closing = screen.getByTestId("popup");
    expect(closing.getAttribute("data-visible")).toBe("false");
    // 닫히는 동안 내용이 사라지면 애니메이션이 빈 상자를 그린다 — `displayed` 캐시가 막는다.
    expect(screen.getByText("삭제 확인")).toBeTruthy();
    expect(screen.getByText("정말 삭제할까요?")).toBeTruthy();
  });

  it("취소를 눌러도 같다 (resolve 값은 false)", async () => {
    const user = userEvent.setup();
    render(<MessagePopup />);

    let resolved: boolean | undefined;
    act(() => {
      void showMessage("나가기", "저장하지 않고 나갈까요?", { type: "confirm" }).then((v) => {
        resolved = v;
      });
    });

    await screen.findByTestId("popup");
    await user.click(screen.getByRole("button", { name: "취소" }));

    await waitFor(() => expect(resolved).toBe(false));
    expect(screen.getByTestId("popup").getAttribute("data-visible")).toBe("false");
  });
});

describe("messageStore — 다음 메시지는 닫힘 애니메이션 뒤에 열린다 (#394)", () => {
  it("resolveMessage 직후에는 큐가 안 열리고, MESSAGE_CLOSE_ANIMATION_MS 뒤에 열린다", async () => {
    vi.useFakeTimers();

    void showMessage("첫 번째", "a");
    await vi.advanceTimersByTimeAsync(0);
    expect(useMessageStore.getState().currentMessage?.title).toBe("첫 번째");

    // 두 번째는 첫 번째가 떠 있는 동안 쌓는다. 여기서 재는 것은 큐 순서가 아니라 "닫힘
    // 애니메이션 뒤에 열린다"는 타이밍이다 — 같은 tick 에 두 건을 넣는 경로(한때 첫 건이
    // 조용히 버려졌다)는 `tests/regressions/408-message-queue-same-tick.test.ts` 가 본다.
    void showMessage("두 번째", "b");
    await vi.advanceTimersByTimeAsync(0);
    expect(useMessageStore.getState().currentMessage?.title).toBe("첫 번째");

    act(() => {
      useMessageStore.getState().resolveMessage(true);
    });
    expect(useMessageStore.getState().currentMessage).toBeNull();

    // 애니메이션(150ms)이 끝나기 직전에는 아직 다음이 안 열려 있어야 한다.
    await vi.advanceTimersByTimeAsync(MESSAGE_CLOSE_ANIMATION_MS - 1);
    expect(useMessageStore.getState().currentMessage).toBeNull();

    await vi.advanceTimersByTimeAsync(1);
    expect(useMessageStore.getState().currentMessage?.title).toBe("두 번째");
  });
});
