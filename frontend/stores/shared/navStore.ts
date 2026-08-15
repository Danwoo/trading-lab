"use client";

import { create } from "zustand";
import { fetchNavigation } from "@/services/common/menuService";

interface NavItem {
  id: string;
  text: string;
  icon?: string;
  path?: string;
  items?: NavItem[];
}

interface NavStore {
  items: NavItem[];
  loaded: boolean;
  error: boolean;
  fetchNav: () => Promise<void>;
  reset: () => void;
  getAllPaths: () => string[];
}

const collectPaths = (items: NavItem[]): string[] =>
  items.flatMap((item) => [...(item.path ? [item.path] : []), ...(item.items ? collectPaths(item.items) : [])]);

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

  getAllPaths: () => collectPaths(get().items),
}));
