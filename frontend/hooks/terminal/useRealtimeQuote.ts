"use client";

import { useRealtimeState } from "@/stores/terminal/realtimeStore";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import type { Quote } from "@/lib/terminal/realtimeArbiter";
import type { PanelData } from "@/types/terminal/provenance";

/**
 * ② 실시간 갈래 — 호가·체결. 구독을 걸지 않는다. "현재 문맥 종목의 실시간 값을 읽는다"만
 * 한다 (§3.6) — 구독의 존재는 `realtimeStore`(구독 중재자)만 안다.
 */
export function useRealtimeQuote(): PanelData<Quote> {
  const state = useRealtimeState();

  switch (state.status) {
    case "subscribed":
      return {
        data: state.quote,
        isLoading: false,
        error: null,
        provenance: { kind: "live", source: "실시간 시세", asOf: state.quote?.at ?? null },
      };
    case "connecting":
      return {
        data: null,
        isLoading: true,
        error: null,
        provenance: { kind: "placeholder", source: "임시 데이터" },
      };
    case "unavailable":
      return {
        data: null,
        isLoading: false,
        error: null,
        provenance: { kind: "placeholder", source: "임시 데이터" },
      };
    case "error":
      return {
        data: null,
        isLoading: false,
        error: state.error,
        provenance: {
          kind: "unavailable",
          reason: state.error ? getApiErrorMessage(state.error) : "실시간 시세를 가져오지 못했습니다",
        },
      };
    case "idle":
    default:
      return {
        data: null,
        isLoading: false,
        error: null,
        provenance: { kind: "unavailable", reason: "선택된 종목이 없습니다" },
      };
  }
}
