"use client";

import { useEffect, useRef, useState } from "react";
import { requestQueue } from "@/lib/terminal/requestQueue";
import { classifyMarketDataError } from "@/lib/terminal/marketDataError";
import type { PanelData } from "@/types/terminal/provenance";

/**
 * ③ 요청형 갈래 — 공시·뉴스·재무·문서. 패널이 열려 있고 보일 때만(`enabled`) 요청한다 (§3.6).
 *
 * `group` 은 문맥 세대 키다 — 값이 바뀌면 이전 세대를 `abortGroup` 하고 다시 요청한다. 그래서
 * 호출자가 세대 키에 재조회 토큰을 섞으면 그것이 곧 refetch 다(별도 reload API 를 두지 않는다).
 *
 * `asOf` 가 `null` 을 허용하는 이유: 기준 시각이 응답에 없는 조회도 있다(예: 이력 목록이 비었을
 * 때). `Provenance` 가 이미 `string | null` 이므로 여기서 빈 문자열을 지어내지 않는다.
 */
export function useOnDemand<T>(params: {
  group: string;
  enabled: boolean;
  source: string;
  fetcher: (signal: AbortSignal) => Promise<{ items: T; asOf: string | null }>;
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
