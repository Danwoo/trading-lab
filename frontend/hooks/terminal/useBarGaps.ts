"use client";

import { useOnDemand } from "@/hooks/terminal/useOnDemand";
import { selectBarGaps, type BarGaps } from "@/services/terminal/marketService";
import { useTerminalRange, useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { barSignalKey, useIngestRevision } from "@/stores/terminal/ingestSignalStore";
import type { PanelData } from "@/types/terminal/provenance";

/**
 * 선택된 종목·기간의 결측 거래일 — 요청형 갈래(③). 문맥은 스스로 읽는다(FE-AD-9).
 *
 * 종목이나 기간이 없으면 요청하지 않는다 — `enabled: false` 로 두면 `useOnDemand` 가 초기
 * 상태(임시 데이터)를 유지한다. "빠진 날이 없다"와 "아직 안 물어봤다"는 다르므로, 호출자는
 * `data === null` 로 그 둘을 가른다.
 */
export function useBarGaps(enabled: boolean): PanelData<BarGaps> {
  const symbol = useTerminalSymbol();
  const range = useTerminalRange();
  const ready = enabled && symbol !== null && symbol.market !== "" && range !== null;
  // 세대 키에 섞는다 — `useOnDemand` 는 `group` 이 바뀌면 다시 요청한다(#350).
  const ingestRevision = useIngestRevision(symbol === null ? null : barSignalKey(symbol.market, symbol.ticker));

  return useOnDemand<BarGaps>({
    group: `bar-gaps:${symbol?.market ?? ""}:${symbol?.ticker ?? ""}:${range?.from ?? ""}:${range?.to ?? ""}:${ingestRevision}`,
    enabled: ready,
    source: "적재 완결성",
    fetcher: async () => {
      const gaps = await selectBarGaps({
        ticker: symbol!.ticker,
        market: symbol!.market,
        from: range!.from,
        to: range!.to,
      });
      // 갭은 조회 시점 계산이라 서버가 기준 시각을 주지 않는다 — 없는 값을 지어내지 않는다.
      return { items: gaps, asOf: null };
    },
  });
}
