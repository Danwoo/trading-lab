"use client";

import { useEffect } from "react";

/**
 * MDI 탭 본문(iframe)이 「저장 안 한 입력이 있다」를 셸에 알리는 통로 (#360).
 *
 * 탭 본문은 iframe 이라 셸과 자바스크립트 문맥이 갈린다 — 폼 상태는 iframe 안 React state 이고,
 * 탭을 닫으면 그 문서가 통째로 사라져 **입력이 경고 없이 없어졌다.** 셸이 막으려면 먼저 알아야
 * 하고, 경계를 넘는 값싼 길이 `postMessage` 다.
 *
 * 같은 출처끼리만 오간다 — 보내는 쪽은 `targetOrigin` 을 자기 출처로 고정하고, 받는 쪽
 * (`GlobalTabs`)은 `event.origin` 을 확인한다.
 *
 * iframe 밖(셸 없이 그 화면을 직접 연 경우)에서는 아무것도 보내지 않는다.
 */
export const UNSAVED_TAB_MESSAGE = "mdi:unsaved";

export interface UnsavedTabMessage {
  type: typeof UNSAVED_TAB_MESSAGE;
  /** 어느 탭인지 — 셸의 `OpenedTab.path` 와 맞춘다. */
  path: string;
  dirty: boolean;
}

export function useUnsavedTabSignal(isDirty: boolean): void {
  useEffect(() => {
    if (typeof window === "undefined" || window.parent === window) return;

    const post = (dirty: boolean) => {
      const message: UnsavedTabMessage = { type: UNSAVED_TAB_MESSAGE, path: window.location.pathname, dirty };
      window.parent.postMessage(message, window.location.origin);
    };

    post(isDirty);
    // 폼이 사라지면(다른 화면으로 이동·언마운트) 남아 있던 표시도 함께 걷는다.
    return () => post(false);
  }, [isDirty]);
}
