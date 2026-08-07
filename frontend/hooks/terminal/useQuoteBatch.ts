"use client";

import { useEffect, useState } from "react";
import { QUOTE_BATCH_INTERVAL_MS } from "@/constants/terminal";
import { classifyMarketDataError } from "@/lib/terminal/marketDataError";
import { selectQuoteBatch } from "@/services/terminal/marketService";
import type { Quote } from "@/lib/terminal/realtimeArbiter";
import type { Provenance } from "@/types/terminal/provenance";

const PLACEHOLDER_PROVENANCE: Provenance = { kind: "placeholder", source: "임시 데이터" };

/**
 * 사이드바 다종목 시세 — 일괄 폴링 훅 하나가 소유한다 (FR-048). 이 훅 밖에서 다종목 시세를
 * 조회하지 않는다. 언마운트 시 타이머를 정리하고, `document.hidden` 인 동안은 폴링을 멈춘다.
 *
 * `market` 을 함께 받는 이유: 같은 티커가 국내·미국에 동시에 존재할 수 있어 티커만으로는 어느
 * 시장을 물어야 할지 정해지지 않는다. 시장별로 시세 소스가 다르므로(MD-AD-17) 이 축이 없으면
 * 서버가 소스를 고를 수 없다.
 */
export function useQuoteBatch(symbols: Array<{ ticker: string; market: string }>): {
  quotes: Record<string, Quote>;
  provenance: Provenance;
} {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [provenance, setProvenance] = useState<Provenance>(PLACEHOLDER_PROVENANCE);
  const tickersKey = symbols.map(({ market, ticker }) => `${market}:${ticker}`).join(",");

  useEffect(() => {
    if (symbols.length === 0) return;

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function fetchOnce(): Promise<void> {
      try {
        const result = await selectQuoteBatch(symbols);
        if (cancelled) return;
        setQuotes(result.items);
        // 한 종목도 못 받았고 사유가 있으면 그 사유를 그대로 보여준다 — 빈 시세를 "실시간"
        // 이라 부르면 왜 비었는지가 화면에서 사라진다 (FR-021).
        const reasons = Object.values(result.unavailable);
        if (Object.keys(result.items).length === 0 && reasons.length > 0) {
          setProvenance({ kind: "unavailable", reason: reasons[0] });
          return;
        }
        setProvenance({ kind: "live", source: result.source, asOf: result.asOf });
      } catch (error) {
        if (cancelled) return;
        const outcome = classifyMarketDataError(error);
        if (outcome.kind === "placeholder") {
          setProvenance(PLACEHOLDER_PROVENANCE);
          return;
        }
        setProvenance({ kind: "unavailable", reason: outcome.error.message });
      }
    }

    function startPolling(): void {
      if (timer !== null) return;
      void fetchOnce();
      timer = setInterval(() => void fetchOnce(), QUOTE_BATCH_INTERVAL_MS);
    }

    function stopPolling(): void {
      if (timer === null) return;
      clearInterval(timer);
      timer = null;
    }

    function handleVisibilityChange(): void {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    }

    if (typeof document !== "undefined") {
      if (!document.hidden) startPolling();
      document.addEventListener("visibilitychange", handleVisibilityChange);
    } else {
      startPolling();
    }

    return () => {
      cancelled = true;
      stopPolling();
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
    };
    // symbols 배열은 매 렌더 새 참조일 수 있어 tickersKey(내용 기준)로만 재구독한다.
  }, [tickersKey]);

  return { quotes, provenance };
}
