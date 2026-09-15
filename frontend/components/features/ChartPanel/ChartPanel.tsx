"use client";

import { useEffect, useRef } from "react";
import { PanelUnavailable } from "@/components/features/Terminal/PanelUnavailable";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { NO_CONTEXT_REASON, useLoadedSeries } from "@/hooks/terminal/useLoadedSeries";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { createCandleChart, type CandleChartHandle } from "@/lib/terminal/candleChart";
import { simpleMovingAverage } from "@/lib/terminal/indicators";
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
 * | 종목/기간을 아직 안 골랐다 (`NO_CONTEXT_REASON`) | **빈 격자** + 무엇을 기다리는지 |
 * | 키가 아직 없다 (`credential_missing`) | **빈 격자** + 해칭 + **사유를 실은** `placeholder` 배지 |
 * | 그 밖의 `unavailable` (소스 없음·제공 범위 밖·상류 장애) | **사유 문장** |
 *
 * **임시 캔들은 그리지 않는다** (리드 결정 2026-09-14). 종전에는 골조를 보여주려고 시드 난수
 * 120영업일을 그렸는데(결정 로그 2026-07-28), 그것은 **종목이 달라도 같은 모양**이라 하나만
 * 보고 있으면 진짜인지 가릴 단서가 화면에 없다 — 정보 패널에서 74,200원을 지운 것과 같은
 * 이유다(#445 F11). 해칭과 배지가 붙어 있어도 「그럴듯한 값」이 남아 있는 한 오독은 가능하다.
 * 리드 결정(2026-09-02 Q1)은 **오독이 원리적으로 불가능한 표시**이고, 캔들에서 그것은
 * 「아무 캔들도 없음」이다.
 *
 * 자리는 지킨다 — 캔버스는 마운트된 채로 두고 위에 사유를 덮는다. 값이 실제로 오면 차트를
 * 처음부터 다시 만들지 않아도 된다.
 */
/** 그릴 값이 없을 때 하는 말 — 지어낸 캔들 대신 이 문장이 선다. */
const NOTHING_TO_DRAW = "아직 그릴 값이 없습니다. 종목과 기간을 고르면 적재된 캔들이 여기 그려집니다.";

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
  // 임시일 때 그릴 것은 **없다.** 그릴 값이 없으면 지어낸 값이 화면에 남을 자리도 없다.
  const candles: Candle[] = isPlaceholder ? [] : (series.data ?? []);
  const placeholderHint = series.provenance.kind === "placeholder" ? series.provenance.hint : undefined;

  useEffect(() => {
    // 실려 온 사유(키가 아직 없다)는 `hint` 로 그대로 넘긴다 — 떨어뜨리면
    // 「키를 넣어야 진짜 값이 온다」가 화면에서 사라진다.
    const effective: Provenance = isPlaceholder
      ? {
          kind: "placeholder",
          source: "임시 데이터",
          note: symbol?.ticker,
          hint: series.provenance.kind === "placeholder" ? series.provenance.hint : undefined,
        }
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
          <div className="absolute inset-0 bg-bg-panel">
            <PanelUnavailable reason={unavailableReason} />
          </div>
        )}
        {/* 임시 상태에서도 **왜** 비어 있는지 말한다 — 빈 격자만 두면 「고장」으로 읽힌다.
            배경을 덮지 않아 `PanelFrame` 의 해칭이 그대로 비친다. */}
        {unavailableReason === null && isPlaceholder && (
          <div className="pointer-events-none absolute inset-0">
            <PanelUnavailable reason={placeholderHint ?? NOTHING_TO_DRAW} />
          </div>
        )}
      </div>
    </div>
  );
}
