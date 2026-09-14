// @vitest-environment jsdom
//
// #443 B-23 — **확인창의 초기 포커스가 「삭제」에 놓이면 안 된다.**
//
// 앞선 회귀 그물(`443-confirm-enter-guard.test.tsx`)은 `Popup` 을 스텁으로 갈아끼운다.
// 그런데 **포커스를 정하는 것이 바로 그 `Popup`** 이라, 그물은 초록인데 결함은 살아 있었다
// (독립 리뷰가 이것을 잡았다 — 「그물은 초록인데 결함은 살아 있는 상태다」).
//
// 그래서 이 그물은 **스텁 없이 실제 `Popup` 을 띄운다.** 확인창의 DOM 순서는 확인(삭제)이
// 먼저이고 취소가 나중인데, `focusInitialTarget` 이 **첫 후보를 무조건** 포커스하므로
// 표식(`autofocus`)은 무시됐다. 포커스된 네이티브 버튼 위의 Enter 는 브라우저 기본 활성화라
// 그대로 삭제가 실행된다 — window 핸들러를 뺀 것만으로는 안 닫힌다.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { Popup } from "@/components/shared/ui/Popup";

afterEach(cleanup);

/** 확인창과 같은 DOM 순서 — 확인(파괴적)이 먼저, 취소가 나중. */
function renderConfirmLike() {
  return render(
    <Popup visible title="확인" onHiding={() => {}}>
      <button data-testid="confirm">삭제</button>
      {/* 앱과 **똑같이** raw 속성으로 넘긴다 — `elementAttr={{ autofocus: "true" }}`.
          React 의 `autoFocus` prop 이 아니므로 React 는 focus() 를 부르지 않는다.
          즉 포커스를 옮길 수 있는 것은 `focusInitialTarget` 뿐이다. */}
      <button data-testid="cancel" {...{ autofocus: "true" }} data-confirm-cancel="true">
        취소
      </button>
    </Popup>,
  );
}

describe("확인창은 파괴적 버튼에 포커스를 두고 열리지 않는다", () => {
  it("표식이 붙은 쪽(취소)이 초기 포커스를 받는다", async () => {
    renderConfirmLike();

    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("cancel")));
  });

  it("파괴적 버튼은 초기 포커스를 받지 않는다", async () => {
    renderConfirmLike();

    await waitFor(() => expect(document.activeElement).not.toBe(screen.getByTestId("confirm")));
  });

  it("표식이 없으면 종전대로 첫 후보가 받는다 — 알림창의 Enter 편의를 안 잃는다", async () => {
    render(
      <Popup visible title="알림" onHiding={() => {}}>
        <button data-testid="ok">확인</button>
        <button data-testid="second">그밖</button>
      </Popup>,
    );

    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("ok")));
  });
});
