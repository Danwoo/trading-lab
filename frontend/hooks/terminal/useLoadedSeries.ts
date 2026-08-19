"use client";

import { useEffect, useState } from "react";
import { requestQueue } from "@/lib/terminal/requestQueue";
import { classifyMarketDataError, provenanceForUnavailable } from "@/lib/terminal/marketDataError";
import { selectCandles } from "@/services/terminal/marketService";
import type { Candle } from "@/services/terminal/marketService";
import { useTerminalInterval, useTerminalRange, useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import type { PanelData } from "@/types/terminal/provenance";

/**
 * 문맥이 아직 없는 상태의 사유. **패널이 이 문자열을 알아야 하는 이유**: "종목/기간을 아직 안
 * 골랐다"(찰나의 정상 상태)와 "소스가 없어 못 채운다"(진짜 사유)는 둘 다 `unavailable` 이지만
 * 화면이 달라야 한다 — 전자는 임시 데이터로 겉모습을 보여도 되고, 후자는 그러면 거짓말이 된다.
 */
export const NO_CONTEXT_REASON = "선택된 종목 또는 기간이 없습니다";

const NO_CONTEXT_STATE: PanelData<Candle[]> = {
  data: null,
  isLoading: false,
  error: null,
  provenance: { kind: "unavailable", reason: NO_CONTEXT_REASON, because: "not-chosen" },
};

/** ① 적재본 갈래 — 과거 캔들. 문맥(종목·주기·기간)을 스스로 읽는다 (§3.6). */
export function useLoadedSeries(): PanelData<Candle[]> {
  const symbol = useTerminalSymbol();
  const interval = useTerminalInterval();
  const range = useTerminalRange();

  const [state, setState] = useState<PanelData<Candle[]>>(NO_CONTEXT_STATE);

  useEffect(() => {
    if (!symbol || !range) {
      setState(NO_CONTEXT_STATE);
      return;
    }

    const group = `${symbol.ticker}:${interval}`;
    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    requestQueue
      .enqueue(group, () =>
        selectCandles({ ticker: symbol.ticker, market: symbol.market, interval, from: range.from, to: range.to }),
      )
      .then((result) => {
        if (cancelled) return;
        // 200 인데 비어 있는 응답 — 사유가 함께 온다. 빈 배열을 "데이터 없음"으로 뭉개면
        // 왜 비었는지가 화면에서 사라진다 (FR-021).
        if (result.unavailableReason !== null) {
          setState({
            data: null,
            isLoading: false,
            error: null,
            provenance: provenanceForUnavailable(result.unavailableReason, result.unavailableCode),
          });
          return;
        }
        setState({
          data: result.items,
          isLoading: false,
          error: null,
          provenance: { kind: "loaded", source: result.source, asOf: result.asOf },
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
          provenance: { kind: "unavailable", reason: "적재본을 불러오지 못했습니다" },
        });
      });

    return () => {
      cancelled = true;
      requestQueue.abortGroup(group);
    };
  }, [symbol?.ticker, symbol?.market, interval, range?.from, range?.to]);

  return state;
}
