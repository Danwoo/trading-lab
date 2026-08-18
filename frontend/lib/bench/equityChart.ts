"use client";

import { AreaSeries, ColorType, LineSeries, createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";

export interface EquityChartPoint {
  time: string;
  value: number;
}

export interface EquityChartHandle {
  /** 자산곡선(금액)과 낙폭(%) — 둘 다 호출자가 픽셀 단위로 다운샘플해 넘긴다 (스펙 §5). */
  setSeries(equity: EquityChartPoint[], drawdownPct: EquityChartPoint[]): void;
  resize(): void;
  destroy(): void;
}

// globals.css 의 "R G B" 채널 문자열을 읽는다 — candleChart.ts 와 같은 규약(#313).
function readChannels(container: HTMLElement, variable: string, fallbackChannels: string): string {
  const value = getComputedStyle(container).getPropertyValue(variable).trim();
  return value.length > 0 ? value : fallbackChannels;
}

function toUtcTimestamp(time: string): UTCTimestamp {
  return Math.floor(Date.parse(time) / 1000) as UTCTimestamp;
}

/**
 * 자산곡선 + 낙폭 차트 (#203). 비-가격 차트도 캔들과 같은 `lightweight-charts` 로 그린다 —
 * FE-AD-2 개정(2026-08-17)의 「필요해지는 시점에 다시 고른다, 그때 lightweight-charts 로
 * 되는지도 함께 본다」의 그 시점이고, 라이브러리를 하나로 유지하는 것이 그 결정이 막는 것이다.
 *
 * `lightweight-charts` 의 타입은 이 파일과 `lib/terminal/candleChart.ts` 밖으로 나가지 않는다
 * (#242 O6 계약의 확장). 색은 호출 시점의 CSS 변수를 읽어 모드 전환을 그대로 따른다.
 *
 * 곡선은 무채(잉크)로, 낙폭만 데이터색(`--market-down`)을 갖는다 — 「색을 갖는 것은
 * 데이터뿐」(디자인 시스템 §0)에서 낙폭은 하락 데이터라 그 색이 맞다.
 */
export function createEquityChart(container: HTMLElement): EquityChartHandle {
  const inkChannels = readChannels(container, "--ink", "230 228 224");
  const downChannels = readChannels(container, "--market-down", "74 140 200");
  const gridColor = `rgb(${readChannels(container, "--hairline", "38 43 48")})`;
  const textColor = `rgb(${readChannels(container, "--ink-muted", "139 135 127")})`;
  const bgColor = `rgb(${readChannels(container, "--bg-panel", "22 25 28")})`;

  const chart: IChartApi = createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: bgColor },
      textColor,
    },
    grid: {
      vertLines: { color: gridColor },
      horzLines: { color: gridColor },
    },
    rightPriceScale: { borderColor: gridColor },
    timeScale: { borderColor: gridColor },
  });

  const equitySeries: ISeriesApi<"Line"> = chart.addSeries(LineSeries, {
    color: `rgb(${inkChannels})`,
    lineWidth: 2,
    priceLineVisible: false,
    // 기본 포맷은 "12000000.00" — 자산 금액은 소수점 없이 자릿수 구분으로 읽힌다.
    priceFormat: { type: "custom", formatter: (v: number) => Math.round(v).toLocaleString("ko-KR") },
  });

  // 낙폭은 아래 20% 띠에 %로 그린다 — 거래량 서브차트와 같은 배치 기법(candleChart.ts).
  const drawdownSeries: ISeriesApi<"Area"> = chart.addSeries(AreaSeries, {
    lineColor: `rgb(${downChannels})`,
    topColor: `rgb(${downChannels} / 0.28)`,
    bottomColor: `rgb(${downChannels} / 0.05)`,
    lineWidth: 1,
    priceScaleId: "drawdown",
    priceLineVisible: false,
    priceFormat: { type: "custom", formatter: (v: number) => `${v.toFixed(1)}%` },
  });
  drawdownSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

  return {
    setSeries(equity, drawdownPct) {
      equitySeries.setData(equity.map((p) => ({ time: toUtcTimestamp(p.time), value: p.value })));
      drawdownSeries.setData(drawdownPct.map((p) => ({ time: toUtcTimestamp(p.time), value: p.value })));
      chart.timeScale().fitContent();
    },

    resize() {
      const { clientWidth, clientHeight } = container;
      // 접힌·과도기 상태에서 캔버스가 0 크기로 잡히는 것을 막는다(#242 O6 위험 표).
      if (clientWidth === 0 || clientHeight === 0) return;
      chart.resize(clientWidth, clientHeight);
    },

    destroy() {
      chart.remove();
    },
  };
}
