"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PersistStorage, StorageValue } from "zustand/middleware";
import { cloneLayout, DEFAULT_LAYOUT } from "@/lib/terminal/layoutDefaults";
import { migrateLayout } from "@/lib/terminal/layoutSchema";
import type { TerminalLayout } from "@/types/terminal/layout";

export interface LayoutStoreState {
  layout: TerminalLayout;
  workspaceId: string | null;
  recovered: boolean;
  setWorkspace: (workspaceId: string) => void;
  toggleCollapsed: (instanceId: string) => void;
  closePanel: (instanceId: string) => void;
  /** 닫은 패널을 되돌리는 유일한 경로 — 자유 배치와 함께 「패널 추가」 목록이 사라졌다 */
  resetPanels: () => void;
  updateSettings: (instanceId: string, settings: Record<string, unknown>) => void;
  dismissRecovered: () => void;
}

interface LayoutPersistedState {
  layout: TerminalLayout;
}

const LAYOUT_STORAGE_PREFIX = "terminal-layout";

function layoutStorageKey(workspaceId: string): string {
  return `${LAYOUT_STORAGE_PREFIX}:${workspaceId}`;
}

/**
 * `setWorkspace` 가 `rehydrate()` 를 트리거하기 직전에 적어 두는 목적지 워크스페이스.
 * `merge()` 는 persist 내부의 원본(un-wrapped) `set()` 만 거치므로 여기서 함께 반영해야
 * `workspaceId` 가 새 값으로 갱신된다 — 그리고 이 경로는 `setItem` 을 부르지 않아 "읽기 전에
 * 기본값을 먼저 써서 저장본을 덮어쓰는" 경합이 생기지 않는다.
 */
let pendingWorkspaceId: string | null = null;

/**
 * `localStorage` 를 직접 감싼다(createJSONStorage 를 쓰지 않는다) — 저장값의 JSON 구문 자체가
 * 깨진 경우(사람이 devtools 에서 손상)도 `migrateLayout` 의 폴백 경로로 흘려보내기 위함이다.
 * createJSONStorage 는 파싱 실패를 그대로 던져 hydrate 체인이 조용히 멈춘다(복구·알림 없이).
 */
const layoutPersistStorage: PersistStorage<LayoutPersistedState> = {
  getItem: (name) => {
    let raw: string | null;
    try {
      raw = localStorage.getItem(name);
    } catch {
      return null;
    }
    if (raw === null) return null;
    try {
      return JSON.parse(raw) as StorageValue<LayoutPersistedState>;
    } catch {
      return { state: { layout: raw as unknown as TerminalLayout }, version: 0 };
    }
  },
  setItem: (name, value) => {
    try {
      localStorage.setItem(name, JSON.stringify(value));
    } catch {
      // 사생활 보호 모드 등 저장소를 못 쓰는 환경에서도 화면은 계속 동작해야 한다
    }
  },
  removeItem: (name) => {
    try {
      localStorage.removeItem(name);
    } catch {
      // 위와 동일
    }
  },
};

/**
 * 워크스페이스별 저장 키 격리(FR-024). `skipHydration: true` 로 두어 스토어 생성 시점(모듈
 * 평가)에 `localStorage` 를 동기로 읽지 않는다 — 실제 읽기는 `setWorkspace` 가 호출될 때만
 * 일어난다. 호출자(O3)는 이것을 마운트 이펙트에서 불러야 한다(렌더 중 호출 시 RGL 스파이크가
 * 실측한 `Minified React error #418` 재현 조건과 같아진다).
 */
export const useLayoutStore = create<LayoutStoreState>()(
  persist(
    (set, _get, api) => ({
      layout: cloneLayout(DEFAULT_LAYOUT),
      workspaceId: null,
      recovered: false,

      setWorkspace: (workspaceId) => {
        pendingWorkspaceId = workspaceId;
        api.persist.setOptions({ name: layoutStorageKey(workspaceId) });
        void api.persist.rehydrate();
      },

      toggleCollapsed: (instanceId) =>
        set((state) => ({
          layout: {
            ...state.layout,
            panels: state.layout.panels.map((panel) =>
              panel.instanceId === instanceId ? { ...panel, collapsed: !panel.collapsed } : panel,
            ),
          },
        })),

      closePanel: (instanceId) =>
        set((state) => ({
          layout: {
            ...state.layout,
            panels: state.layout.panels.filter((panel) => panel.instanceId !== instanceId),
          },
        })),

      resetPanels: () => set({ layout: cloneLayout(DEFAULT_LAYOUT) }),

      updateSettings: (instanceId, settings) =>
        set((state) => ({
          layout: {
            ...state.layout,
            panels: state.layout.panels.map((panel) =>
              panel.instanceId === instanceId ? { ...panel, settings } : panel,
            ),
          },
        })),

      dismissRecovered: () => set({ recovered: false }),
    }),
    {
      name: layoutStorageKey("default"),
      storage: layoutPersistStorage,
      skipHydration: true,
      partialize: (state) => ({ layout: state.layout }),
      merge: (persisted, current) => {
        const persistedLayout =
          persisted && typeof persisted === "object" && "layout" in persisted
            ? (persisted as LayoutPersistedState).layout
            : undefined;
        const { layout, recovered } = migrateLayout(persistedLayout);
        return { ...current, workspaceId: pendingWorkspaceId, layout, recovered };
      },
    },
  ),
);
