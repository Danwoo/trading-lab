"use client";

import { useEffect, useRef } from "react";
import { PanelUnavailable } from "@/components/features/Terminal/PanelUnavailable";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { NO_CONTEXT_REASON, useLoadedSeries } from "@/hooks/terminal/useLoadedSeries";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { createCandleChart, type CandleChartHandle } from "@/lib/terminal/candleChart";
import { simpleMovingAverage } from "@/lib/terminal/indicators";
import { SAMPLE_CANDLES } from "@/lib/terminal/sampleCandles";
import type { Candle } from "@/services/terminal/marketService";
import type { Provenance } from "@/types/terminal/provenance";
import type { PanelProps } from "@/types/terminal/panel";
import { ChartToolbar, MOVING_AVERAGE_PERIODS } from "./ChartToolbar";

interface ChartPanelSettings {
  movingAverages?: number[];
}

function readMovingAverages(settings: Record<string, unknown>): number[] {
  const raw = (settings as ChartPanelSettings).movingAverages;
  if (!Array.isArray(raw)) return [];
  const allowed = new Set<number>(MOVING_AVERAGE_PERIODS);
  return raw.filter((period): period is number => typeof period === "number" && allowed.has(period));
}

/**
 * 캔들·거래량·이동평균 패널(#242 O6, FR-016·FR-017).
 *
 * 세 상태를 **다르게** 그린다 — 이 구분이 FR-021("왜 비어 있는지 말한다")의 화면 쪽 끝이다:
 *
 * | 상태 | 그리는 것 |
 * |---|---|
 * | 적재본이 있다 | 실캔들 + `loaded` 출처(소스·수정주가 정책·기준시각) |
 * | 종목/기간을 아직 안 골랐다 (`NO_CONTEXT_REASON`) | `SAMPLE_CANDLES` + `placeholder` 배지 |
 * | 그 밖의 `unavailable` (소스 없음·키 없음·미적재) | **사유 문장** — 임시 캔들을 그리지 않는다 |
 *
 * 세 번째 줄이 요점이다. 키가 없어 비어 있는 차트에 그럴싸한 임시 캔들을 그리면 "데이터가
 * 들어왔다"로 읽힌다 — 그것이 NFR-001 이 막으려는 상태다.
 */
export default function ChartPanel({ instanceId, settings, onSettingsChange }: PanelProps) {
  const symbol = useTerminalSymbol();
  const series = useLoadedSeries();
  const reportProvenance = usePanelProvenance(instanceId);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<CandleChartHandle | null>(null);

  const activeMovingAverages = readMovingAverages(settings);

  // `ChartToolbar` 가 마운트 시 기본 기간을 채우기 전 찰나의 상태 — 이때만 겉모습을 임시
  // 캔들로 보여준다. 사유 문자열로 가리는 이유는, "문맥 없음"과 "소스 없음"이 타입상 같은
  // `unavailable` 이라 종류를 구분할 다른 축이 없기 때문이다.
  const isNoContextYet = series.provenance.kind === "unavailable" && series.provenance.reason === NO_CONTEXT_REASON;
  const isPlaceholder = series.provenance.kind === "placeholder" || isNoContextYet;
  const unavailableReason =
    series.provenance.kind === "unavailable" && !isNoContextYet ? series.provenance.reason : null;
  const candles: Candle[] = isPlaceholder ? SAMPLE_CANDLES : (series.data ?? []);

  useEffect(() => {
    const effective: Provenance = isPlaceholder
      ? { kind: "placeholder", source: "임시 데이터", note: symbol?.ticker }
      : series.provenance;
    reportProvenance(effective);
    // series.provenance 원본을 deps 에 두면(현재는 useState 기반이라 안전하지만) 나중에
    // useLoadedSeries 구현이 바뀌어 매 렌더 새 객체를 반환하게 되면 report→재렌더→다시 report
    // 로 무한 루프가 될 수 있다(SymbolInfoPanel 에서 실측). 내용 기준 키(JSON)로 방어한다.
  }, [isPlaceholder, JSON.stringify(series.provenance), symbol?.ticker, reportProvenance]);

  // 차트 마운트 — 인스턴스당 한 번. PanelFrame 이 접힌 상태에서는 이 컴포넌트를 아예 렌더하지
  // 않으므로(children 전체를 다른 분기로 스왑) 접힘 상태에서 캔버스가 0 크기로 잡히는 일은
  // 애초에 일어나지 않는다(#242 O6 위험 표).
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handle = createCandleChart(container);
    chartRef.current = handle;
    return () => {
      handle.destroy();
      chartRef.current = null;
    };
  }, []);

  // 패널 크기 변화(그리드 리사이즈)를 캔버스가 따라가게 한다 — 대표적 실패 지점 방어.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => chartRef.current?.resize());
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    chartRef.current?.setCandles(candles);
  }, [candles]);

  useEffect(() => {
    const handle = chartRef.current;
    if (!handle) return;
    for (const period of MOVING_AVERAGE_PERIODS) {
      const id = `ma-${period}`;
      if (activeMovingAverages.includes(period)) {
        handle.setOverlay(id, simpleMovingAverage(candles, period));
      } else {
        handle.removeOverlay(id);
      }
    }
    // activeMovingAverages 는 매 렌더 새 배열 참조라 내용 기준 키(join)로 비교한다.
  }, [activeMovingAverages.join(","), candles]);

  const handleToggleMovingAverage = (period: number) => {
    const next = activeMovingAverages.includes(period)
      ? activeMovingAverages.filter((p) => p !== period)
      : [...activeMovingAverages, period];
    onSettingsChange({ ...settings, movingAverages: next });
  };

  return (
    <div className="flex h-full flex-col">
      <ChartToolbar activeMovingAverages={activeMovingAverages} onToggleMovingAverage={handleToggleMovingAverage} />
      {/* 사유가 있을 때도 캔버스는 마운트된 채로 둔다 — 언마운트하면 기간을 바꿔 데이터가
          들어온 순간 차트를 처음부터 다시 만들게 된다. 대신 위에 사유를 덮어 보여준다. */}
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="h-full w-full" />
        {unavailableReason !== null && (
          <div className="absolute inset-0 bg-slate-panel">
            <PanelUnavailable reason={unavailableReason} />
          </div>
        )}
      </div>
    </div>
  );
}
