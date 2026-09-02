// @vitest-environment jsdom
//
// #443 회귀 그물 — **확인창에서 Enter 한 번이 파괴적 동작을 실행하지 않는다.**
//
// Cycle 7 발굴(B-23)은 「확인창이 「삭제」에 포커스를 두고 열린다」로 보고됐고, 그래서 포커스만
// 옮기면 되는 것처럼 보였다. 코드를 읽으니 원인이 하나 더 있었다 — `MessagePopup` 이 **window 에
// Enter 핸들러를 걸어 `handleConfirm()` 을 부른다.** 포커스가 취소에 있어도 Enter 는 확인으로 갔다.
// 그래서 포커스만 고치면 이 결함은 안 닫힌다.
//
// 증명하는 것: 확인창(type=confirm)에서 Enter 는 확인을 부르지 않는다. 알림창(type=alert)에서는
// 종전대로 닫는다 — 편의를 잃지 않는다.
// 증명하지 못하는 것: 실브라우저에서 초기 포커스가 취소에 놓이는지. jsdom 에는 `autofocus` 의
// 브라우저 동작이 없어 **속성이 취소 버튼 쪽에 붙었는지**까지만 본다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";

import { MessagePopup } from "@/components/shared/Feedback/MessagePopup";
import { showMessage, useMessageStore } from "@/stores/shared/messageStore";

vi.mock("@/components/shared/ui/Popup", () => ({
  Popup: ({ visible, children }: { visible: boolean; children?: React.ReactNode }) => (
    <div data-testid="popup" data-visible={String(visible)}>
      {children}
    </div>
  ),
}));

afterEach(() => {
  cleanup();
  act(() => useMessageStore.setState({ currentMessage: null }));
  vi.restoreAllMocks();
});

function pressEnter() {
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  });
}

describe("확인창에서 Enter 가 파괴적 동작을 실행하지 않는다 (#443)", () => {
  it("type=confirm — Enter 를 눌러도 onConfirm 이 불리지 않는다", async () => {
    const onConfirm = vi.fn();
    render(<MessagePopup />);
    act(() => {
      void showMessage("삭제 확인", "정말 지울까요?", {
        type: "confirm",
        confirmText: "삭제",
        cancelText: "취소",
        callback: { onConfirm, onCancel: vi.fn() },
      });
    });
    await screen.findByTestId("popup");
    expect(screen.getByRole("button", { name: "삭제" })).toBeTruthy();

    pressEnter();

    await waitFor(() => expect(onConfirm).not.toHaveBeenCalled());
  });

  it("type=alert — Enter 는 종전대로 닫는다", async () => {
    const onConfirm = vi.fn();
    render(<MessagePopup />);
    act(() => {
      void showMessage("알림", "저장했습니다", { type: "alert", callback: { onConfirm } });
    });
    await screen.findByTestId("popup");

    pressEnter();

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
  });

  it("확인창의 초기 포커스 대상 표식이 취소 버튼에 붙는다", async () => {
    render(<MessagePopup />);
    act(() => {
      void showMessage("삭제 확인", "정말 지울까요?", {
        type: "confirm",
        confirmText: "삭제",
        cancelText: "취소",
        callback: { onConfirm: vi.fn() },
      });
    });
    await screen.findByTestId("popup");
    expect(document.querySelector('[data-confirm-cancel="true"]')).not.toBeNull();
  });
});
