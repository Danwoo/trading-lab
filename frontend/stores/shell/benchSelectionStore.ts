"use client";

import { create } from "zustand";

/** 무엇을 고른 것인가. 보드의 어느 자리가 반응하는지가 여기서 갈린다 */
export type BenchSelectionKind = "grid-point" | "curve-point" | "bot";

/** 어디서 골랐나 — 반대쪽이 「좁힘」으로 반응할지 「표시」로 반응할지 가른다 */
export type BenchSelectionOrigin = "board" | "panel";

export interface BenchSelection {
  kind: BenchSelectionKind;
  id: string;
  /** 사람이 읽는 이름. 「무엇으로 좁혀졌는지」를 패널 머리에 그대로 쓴다 */
  label: string;
  origin: BenchSelectionOrigin;
}

export interface BenchSelectionState {
  selection: BenchSelection | null;
  select: (selection: BenchSelection) => void;
  clear: () => void;
}

/**
 * 보드와 패널이 **하나의 선택을 공유한다** — 화면 결정 §20.2 「이동 규칙」 셋 중 뒤 둘이
 * 이 스토어다.
 *
 * | 동작 | 결과 |
 * |---|---|
 * | 레일 아이콘 | 그 패널 열림/닫힘. **보드는 안 바뀜** (이 스토어 밖 — 셸 레이아웃의 몫) |
 * | 보드에서 고르기 | `origin: "board"` — 열린 패널의 내용이 그 선택으로 좁혀진다 |
 * | 패널에서 고르기 | `origin: "panel"` — 보드가 그 지점을 표시한다 |
 *
 * **선택은 하나뿐이고 양방향이다.** 보드용·패널용으로 두 벌을 두면 둘이 어긋나는 순간
 * 「보드에서 본 것을 패널에 바로 적용한다」는 이 제품의 핵심이 무너진다. `origin` 은 어느 쪽이
 * 방금 움직였는지만 말한다 — 문구를 고르는 데 쓰고, 값 자체를 가르지 않는다.
 *
 * 화면 폭과 무관하다. 좁은 화면에서 패널이 보드를 덮어도(§21.6) 선택은 그대로 살아 있고,
 * 패널을 닫으면 보드가 그 지점을 표시한 채로 드러난다.
 */
export const useBenchSelectionStore = create<BenchSelectionState>()((set) => ({
  selection: null,

  select: (selection) =>
    set((state) => {
      const same = state.selection;
      // 고른 것을 다시 고르면 푼다 — 좁힌 것을 되돌릴 길이 「전체 보기」 버튼 하나뿐이면
      // 패널이 닫혀 있는 동안 보드에서 푸는 방법이 없다.
      if (same && same.kind === selection.kind && same.id === selection.id) {
        return { selection: null };
      }
      return { selection };
    }),

  clear: () => set({ selection: null }),
}));
