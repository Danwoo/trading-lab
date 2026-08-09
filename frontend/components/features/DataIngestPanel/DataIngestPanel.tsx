"use client";

import { useCallback, useEffect, useState } from "react";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { useIngestRuns } from "@/hooks/terminal/useIngestRuns";
import { useBarGaps } from "@/hooks/terminal/useBarGaps";
import { useMarketCapabilities } from "@/hooks/terminal/useMarketCapabilities";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import type { PanelProps } from "@/types/terminal/panel";
import { IngestRunForm } from "./IngestRunForm";
import { IngestRunList } from "./IngestRunList";

/**
 * 실행 중인 잡이 있을 때만 다시 물어보는 간격. 큐가 조용하면 폴링하지 않는다 — 아무 일도 없는
 * 화면이 주기적으로 서버를 두드릴 이유가 없다.
 */
const ACTIVE_POLL_MS = 4000;

/**
 * 적재 실행·현황 (FR-010). `tn_ingest_run` 하나가 요청·실행·이력을 겸하므로(M2-AD-12) 잡을
 * 넣는 자리와 결과를 보는 자리가 한 패널이다.
 *
 * **시장 축이 걸리지 않는 패널이다** — `capabilityMatrix` 에서 `dataIngest` 를 시장 무관으로
 * 분류한 이유가 그것이다. 종목을 고르기 전에도 열려야 적재를 시작할 수 있다(종목이 없으면
 * 차트에 그릴 것이 없고, 그리려면 먼저 여기서 받아야 한다).
 */
export default function DataIngestPanel({ instanceId }: PanelProps) {
  const [reloadToken, setReloadToken] = useState(0);
  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  const runs = useIngestRuns(reloadToken, true);
  const gaps = useBarGaps(true);
  const capabilities = useMarketCapabilities(true);
  const symbol = useTerminalSymbol();
  const reportProvenance = usePanelProvenance(instanceId);

  // 이 패널의 본체는 적재 이력이다 — 헤더 배지는 그 조회의 출처를 따른다.
  useEffect(() => {
    reportProvenance(runs.provenance);
    // provenance 는 매 렌더 새 객체 리터럴이라 원본을 deps 에 넣으면 report→재렌더→다시 report
    // 로 무한 루프가 된다(SymbolInfoPanel 과 같은 이유). 내용 기준 키로 비교한다.
  }, [JSON.stringify(runs.provenance), reportProvenance]);

  const activeRuns = (runs.data ?? []).filter((run) => run.status === "queued" || run.status === "running");
  const hasActiveRuns = activeRuns.length > 0;

  useEffect(() => {
    if (!hasActiveRuns) return;
    const timer = window.setInterval(reload, ACTIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveRuns, reload]);

  const blockedSources = (capabilities.data ?? []).filter((row) => !row.available && row.reason !== null);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-3 font-mono text-xs">
      <IngestRunForm onSubmitted={reload} />

      {blockedSources.length > 0 && (
        <section aria-labelledby={`${instanceId}-blocked`}>
          <h3 id={`${instanceId}-blocked`} className="mb-1 text-signal-warn">
            지금 쓸 수 없는 소스
          </h3>
          <ul className="flex flex-col gap-1 text-ink-muted">
            {blockedSources.map((row) => (
              <li key={`${row.source}:${row.market}:${row.dataKind}`}>
                <span className="text-ink-primary">
                  {row.source} · {row.market} · {row.dataKind}
                </span>
                {/* 서버 문구를 그대로 낸다 — .env 항목명과 발급 경로가 여기 실려 온다(설계 §7.4) */}
                <span className="block">{row.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby={`${instanceId}-gaps`}>
        <h3 id={`${instanceId}-gaps`} className="mb-1 text-ink-primary">
          빠진 거래일
        </h3>
        {gaps.data === null ? (
          <p className="text-ink-muted">
            {symbol === null ? "종목을 고르면 그 종목의 빠진 거래일을 확인합니다." : "확인하지 않았습니다."}
          </p>
        ) : gaps.data.missingDates.length === 0 ? (
          <p className="text-ink-muted">
            {gaps.data.dateFrom}~{gaps.data.dateTo} 구간에 빠진 거래일이 없습니다. (휴장일은 세지 않습니다)
          </p>
        ) : (
          <div className="text-signal-warn">
            <p>
              {gaps.data.dateFrom}~{gaps.data.dateTo} 구간에 {gaps.data.missingDates.length}일이 비어 있습니다.
            </p>
            <p className="text-ink-muted">{gaps.data.missingDates.slice(0, 12).join(" · ")}</p>
            {gaps.data.missingDates.length > 12 && (
              <p className="text-ink-muted">…외 {gaps.data.missingDates.length - 12}일</p>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby={`${instanceId}-runs`}>
        <h3 id={`${instanceId}-runs`} className="mb-1 text-ink-primary">
          적재 이력
        </h3>
        {runs.error ? (
          <p role="alert" className="text-market-down">
            이력을 불러오지 못했습니다.
          </p>
        ) : (
          <IngestRunList runs={runs.data ?? []} />
        )}
      </section>
    </div>
  );
}
