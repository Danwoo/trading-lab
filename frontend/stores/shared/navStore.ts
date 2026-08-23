"use client";

import { create } from "zustand";
import { fetchNavigation } from "@/services/common/menuService";
import { httpStatusOf } from "@/utils/common/api/client";

interface NavItem {
  id: string;
  text: string;
  icon?: string;
  path?: string;
  items?: NavItem[];
}

/**
 * 메뉴를 못 받은 사유 — **「서버가 세션을 거부했다」와 「그 밖의 이유로 못 읽었다」는 다른
 * 사건이다.** 하나로 묶으면 둘 중 한쪽에는 반드시 거짓을 말하게 된다 (#333, #335 리뷰).
 *
 * - `unauthenticated` — **401**. 쿠키는 남았는데 서버가 그 세션을 더는 받지 않는다(다른 기기에서
 *   로그아웃 · 세션 폐기 · 계정 삭제 · DB 재시드로 세션 행 소실 · `BETTER_AUTH_SECRET` 교체).
 *   미들웨어(`proxy.ts`)는 쿠키의 **존재만** 보므로 페이지는 그대로 열리고 이 API 만 401 을
 *   낸다 — 여기서 갈라야 사용자가 로그인 화면으로 나갈 수 있다.
 * - `unreadable` — 그 밖 전부. 500·503 처럼 서버가 답을 못 준 것, 그리고 네트워크 단절·
 *   타임아웃처럼 **답이 아예 없는** 것(`httpStatusOf` 가 `undefined`). 403 도 여기다 —
 *   인증은 살아 있고 권한만 모자란 상태라 「로그인은 유지된다」가 참이다.
 */
export type NavFailure = "unauthenticated" | "unreadable";

interface NavStore {
  items: NavItem[];
  loaded: boolean;
  /** 못 받았으면 그 사유, 정상이면 `null`. 불리언 두 개로 두면 서로 모순되는 상태가 표현된다. */
  failure: NavFailure | null;
  fetchNav: () => Promise<void>;
  reset: () => void;
  getAllPaths: () => string[];
}

const collectPaths = (items: NavItem[]): string[] =>
  items.flatMap((item) => [...(item.path ? [item.path] : []), ...(item.items ? collectPaths(item.items) : [])]);

/** 401 만 「세션이 거부됐다」다. 나머지는 상태 코드가 있든 없든 「못 읽었다」로 묶는다. */
const classifyNavFailure = (error: unknown): NavFailure =>
  httpStatusOf(error) === 401 ? "unauthenticated" : "unreadable";

export const useNavStore = create<NavStore>((set, get) => ({
  items: [],
  loaded: false,
  failure: null,

  fetchNav: async () => {
    if (get().loaded) return;
    try {
      const data = await fetchNavigation();
      set({ items: data.items, loaded: true, failure: null });
    } catch (error) {
      set({ items: [], loaded: true, failure: classifyNavFailure(error) });
    }
  },

  reset: () => set({ items: [], loaded: false, failure: null }),

  getAllPaths: () => collectPaths(get().items),
}));
