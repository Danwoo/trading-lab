"use client";

import { useEffect, useRef, useState } from "react";
import { requestQueue } from "@/lib/terminal/requestQueue";
import { classifyMarketDataError } from "@/lib/terminal/marketDataError";
import type { PanelData } from "@/types/terminal/provenance";

/** ③ 요청형 갈래 — 공시·뉴스·재무·문서. 패널이 열려 있고 보일 때만(`enabled`) 요청한다 (§3.6). */
export function useOnDemand<T>(params: {
  group: string;
  enabled: boolean;
  source: string;
  fetcher: (signal: AbortSignal) => Promise<{ items: T; asOf: string }>;
}): PanelData<T> {
  const { group, enabled, source } = params;

  // fetcher 는 호출자가 매 렌더 새로 만들 수 있는 클로저다 — 의존성 배열에 넣으면 그때마다
  // 재요청이 되므로, 최신 값만 ref 로 따라가고 effect 는 group·enabled·source 에만 반응한다.
  const fetcherRef = useRef(params.fetcher);
  useEffect(() => {
    fetcherRef.current = params.fetcher;
  });

  const [state, setState] = useState<PanelData<T>>({
    data: null,
    isLoading: false,
    error: null,
    provenance: { kind: "placeholder", source: "임시 데이터" },
  });

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    requestQueue
      .enqueue(group, (signal) => fetcherRef.current(signal))
      .then((result) => {
        if (cancelled) return;
        setState({
          data: result.items,
          isLoading: false,
          error: null,
          provenance: { kind: "loaded", source, asOf: result.asOf },
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const outcome = classifyMarketDataError(error);
        if (outcome.kind === "placeholder") {
          setState({
            data: null,
            isLoading: false,
            error: null,
            provenance: { kind: "placeholder", source: "임시 데이터" },
          });
          return;
        }
        setState({
          data: null,
          isLoading: false,
          error: outcome.error,
          provenance: { kind: "unavailable", reason: "요청을 처리하지 못했습니다" },
        });
      });

    return () => {
      cancelled = true;
      requestQueue.abortGroup(group);
    };
  }, [group, enabled, source]);

  return state;
}
