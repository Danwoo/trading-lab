"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { MAX_TABS } from "@/constants/app";

export interface OpenedTab {
  id: string;
  title: string;
  path: string;
}

interface TabStore {
  tabs: OpenedTab[];
  activeId: string | null;
  openTab: (tab: OpenedTab) => void;
  closeTab: (id: string) => void;
  setActive: (id: string) => void;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
  closeOthers: (id: string) => void;
  closeAll: () => void;
}

export const useTabStore = create<TabStore>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeId: null,

      openTab: (tab) => {
        const { tabs, activeId } = get();
        const existing = tabs.find((t) => t.id === tab.id);
        if (existing) {
          set({ activeId: tab.id });
          return;
        }
        // 최대 탭 수 초과 시 활성 탭이 아닌 가장 오래된 탭(앞쪽) 제거 (LRU)
        let next = [...tabs, tab];
        while (next.length > MAX_TABS) {
          const victimIdx = next.findIndex((t) => t.id !== activeId && t.id !== tab.id);
          if (victimIdx === -1) break;
          next = [...next.slice(0, victimIdx), ...next.slice(victimIdx + 1)];
        }
        set({ tabs: next, activeId: tab.id });
      },

      closeTab: (id) => {
        const { tabs, activeId } = get();
        const idx = tabs.findIndex((t) => t.id === id);
        if (idx === -1) return;
        const next = tabs.filter((t) => t.id !== id);
        let nextActive = activeId;
        if (activeId === id) {
          nextActive = next[idx]?.id ?? next[idx - 1]?.id ?? null;
        }
        set({ tabs: next, activeId: nextActive });
      },

      setActive: (id) => set({ activeId: id }),

      reorderTabs: (fromIndex, toIndex) => {
        const { tabs } = get();
        if (fromIndex === toIndex) return;
        const next = [...tabs];
        const [moved] = next.splice(fromIndex, 1);
        next.splice(toIndex, 0, moved);
        set({ tabs: next });
      },

      closeOthers: (id) => {
        const keep = get().tabs.find((t) => t.id === id);
        if (!keep) return;
        set({ tabs: [keep], activeId: id });
      },

      closeAll: () => set({ tabs: [], activeId: null }),
    }),
    {
      name: "mdi-tabs",
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);
