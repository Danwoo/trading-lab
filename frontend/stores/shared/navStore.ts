"use client";

import { create } from "zustand";
import { fetchNavigation } from "@/services/common/menuService";
import type { NavItem } from "@/lib/shell/nav";

interface NavStore {
  items: NavItem[];
  loaded: boolean;
  error: boolean;
  fetchNav: () => Promise<void>;
  reset: () => void;
}

/**
 * DB 메뉴 트리 한 벌. 셸 둘이 같은 트리를 각자 읽는다 — 제품 셸은 접근 가능 경로 판정에,
 * 관리 셸은 사이드바 렌더에. 트리를 골라 읽는 함수는 `lib/shell/nav.ts` 가 소유한다.
 */
export const useNavStore = create<NavStore>((set, get) => ({
  items: [],
  loaded: false,
  error: false,

  fetchNav: async () => {
    if (get().loaded) return;
    try {
      const data = await fetchNavigation();
      set({ items: data.items, loaded: true, error: false });
    } catch {
      set({ loaded: true, error: true });
    }
  },

  reset: () => set({ items: [], loaded: false, error: false }),
}));
