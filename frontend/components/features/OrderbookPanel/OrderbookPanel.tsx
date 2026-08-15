"use client";

import { useEffect, useMemo } from "react";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { useMarketCapabilities } from "@/hooks/terminal/useMarketCapabilities";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import type { PanelProps } from "@/types/terminal/panel";
import type { Provenance } from "@/types/terminal/provenance";

const NO_SYMBOL = "종목을 먼저 고르세요 — 사이드바의 관심종목·보유·스크리너 중 하나에서 고릅니다.";

/**
 * 호가 패널 — **아직 소스가 없다.** 그 사실을 화면이 서버에게 물어서 답한다.
 *
 * 사유를 여기서 지어내지 않는 것이 요점이다(설계 §7.4). 호가는 `data_kind` 의 닫힌 집합에
 * 이미 들어 있으므로, 소스가 등록되고 키가 채워지면 이 패널의 사유는 **저절로** 바뀐다 —
 * 문구를 하드코딩하면 그날 화면이 거짓말을 한다.
 *
 * 실데이터를 그리는 일은 적재 파이프라인(#2)에 물려 있어 이번 마일스톤 밖이다.
 */
export default function OrderbookPanel({ instanceId }: PanelProps) {
  const symbol = useTerminalSymbol();
  const reportProvenance = usePanelProvenance(instanceId);
  const capabilities = useMarketCapabilities(symbol !== null);

  const verdict = useMemo(() => {
    if (symbol === null) return { reason: NO_SYMBOL, rows: [] };
    const rows = (capabilities.data ?? []).filter(
      (row) => row.dataKind === "orderbook" && row.market === symbol.market,
    );
    if (rows.length === 0) {
      return {
        reason: `${symbol.market} 시장의 호가를 다루는 소스가 등록되어 있지 않습니다`,
        rows,
      };
    }
    const blocked = rows.filter((row) => !row.available);
    if (blocked.length === rows.length) {
      return { reason: blocked.map((row) => `${row.source}: ${row.reason}`).join(" / "), rows };
    }
    // 소스는 있는데 적재가 없는 상태 — 「소스 없음」과 구분해서 말한다.
    return { reason: `${symbol.ticker} 의 적재된 호가가 아직 없습니다`, rows };
  }, [symbol, capabilities.data]);

  useEffect(() => {
    const provenance: Provenance = { kind: "unavailable", reason: verdict.reason };
    reportProvenance(provenance);
  }, [verdict.reason, reportProvenance]);

  // 사유는 `PanelFrame` 이 `PanelUnavailable` 로 그린다 — 이 컴포넌트는 그동안 아무것도 안 그린다.
  return null;
}
