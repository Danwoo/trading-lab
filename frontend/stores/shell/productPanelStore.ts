"use client";

import { create } from "zustand";

export interface ProductPanelState {
  /** 지금 열려 있는 레일 항목 id. 닫혀 있으면 null */
  openPanelId: string | null;
  /** 에이전트 전용 620px 토글 (§21.3) */
  expanded: boolean;
  /**
   * 포커스를 돌려줄 레일 버튼 id. 패널이 닫히면 그 버튼으로 되돌린다 — 안 돌려주면 사라진
   * 요소에 포커스가 남아 브라우저가 `<body>` 로 떨어뜨리고 키보드 위치를 잃는다.
   */
  focusRailItemId: string | null;
  toggle: (id: string) => void;
  open: (id: string) => void;
  close: () => void;
  toggleExpanded: () => void;
  clearFocusRequest: () => void;
}

/**
 * 어느 패널이 열려 있나 — **셸과 보드가 함께 읽고 쓴다.**
 *
 * 이 값이 셸 레이아웃의 지역 상태였을 때는 레일만 패널을 열 수 있었다. 그런데 §21.4 가 빈
 * 보드에 길을 둘 주라고 못박았고(「봇 만들기」·「에이전트에게 맡기기」), **그 길은 눌렀을 때
 * 실제로 무언가 열려야 한다** — 아무 일도 안 일어나는 버튼이 빈 화면보다 나쁘다. 보드가 셸의
 * 지역 상태를 건드릴 수는 없으므로 소유를 스토어로 옮겼다.
 *
 * 이동 규칙(§20.2)은 그대로다 — 패널을 여닫는 것은 **보드를 바꾸지 않는다**(라우팅이 일어나지
 * 않는다). 보드↔패널의 선택 공유는 여전히 `benchSelectionStore` 의 몫이고, 여기는 「무엇이
 * 열려 있나」만 안다.
 */
export const useProductPanelStore = create<ProductPanelState>()((set) => ({
  openPanelId: null,
  expanded: false,
  focusRailItemId: null,

  toggle: (id) =>
    set((state) => {
      if (state.openPanelId === id) {
        return { openPanelId: null, expanded: false, focusRailItemId: id };
      }
      // 폭 토글은 패널마다 새로 정한다 — 에이전트를 620 으로 넓혀 두고 다른 패널을 열면
      // 그 패널까지 620 이 되는데, §21.3 이 620 을 준 것은 에이전트뿐이다.
      return { openPanelId: id, expanded: false };
    }),

  open: (id) => set({ openPanelId: id, expanded: false }),

  close: () =>
    set((state) => ({
      openPanelId: null,
      expanded: false,
      focusRailItemId: state.openPanelId ?? state.focusRailItemId,
    })),

  toggleExpanded: () => set((state) => ({ expanded: !state.expanded })),

  clearFocusRequest: () => set({ focusRailItemId: null }),
}));
