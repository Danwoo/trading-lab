"use client";

import { useCallback } from "react";
import { create } from "zustand";
import type { Provenance } from "@/types/terminal/provenance";

interface ProvenanceBridgeState {
  byInstanceId: Record<string, Provenance>;
  setProvenance: (instanceId: string, provenance: Provenance) => void;
}

/**
 * 패널(자기 데이터 훅)과 프레임(헤더 배지) 사이의 유일한 통로. 패널은 문맥·레이아웃 스토어를
 * 직접 건드리지 않고 이 다리로만 출처를 올린다 — 프레임은 이 다리로만 그것을 읽는다.
 */
const useProvenanceBridgeStore = create<ProvenanceBridgeState>((set) => ({
  byInstanceId: {},
  setProvenance: (instanceId, provenance) =>
    set((state) => ({ byInstanceId: { ...state.byInstanceId, [instanceId]: provenance } })),
}));

/** 패널이 쓴다 — 자기 데이터 훅이 준 `provenance` 를 이 함수로 한 번 올리기만 한다. */
export function usePanelProvenance(instanceId: string): (provenance: Provenance) => void {
  const setProvenance = useProvenanceBridgeStore((state) => state.setProvenance);
  return useCallback((provenance: Provenance) => setProvenance(instanceId, provenance), [instanceId, setProvenance]);
}

/** 프레임이 읽는다 — 패널이 아직 아무 값도 올리지 않았으면 `null`("출처 미상"). */
export function usePanelProvenanceValue(instanceId: string): Provenance | null {
  return useProvenanceBridgeStore((state) => state.byInstanceId[instanceId] ?? null);
}
