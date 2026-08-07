"use client";

import { CandlestickSeries, ColorType, HistogramSeries, LineSeries, createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import type { Candle } from "@/services/terminal/marketService";

export interface CandleChartHandle {
  setCandles(candles: Candle[]): void;
  setOverlay(id: string, points: Array<{ time: string; value: number }>): void;
  removeOverlay(id: string): void;
  resize(): void;
  destroy(): void;
}

/** 이동평균 등 겹침 선의 순환 팔레트 — 시장색(up/down)과 겹치지 않는 무채색·경고색 계열만 쓴다. */
const OVERLAY_PALETTE = ["#D9A441", "#8AA4C8", "#C9D1DC"] as const;

// `variable` 은 "R G B" 채널 문자열(헤더 없음, styles/globals.css 의 :root 값과 같은 형식,
// #313)을 담는다 — 순수 hex 가 아니다. `lightweight-charts` 는 완성된 CSS 색 문자열을
// 요구하므로 여기서 `rgb(...)` 로 감싸 돌려준다. `fallbackChannels` 도 같은 채널 형식이어야
// 한다.
function readCssColor(container: HTMLElement, variable: string, fallbackChannels: string): string {
  const value = getComputedStyle(container).getPropertyValue(variable).trim();
  return `rgb(${value.length > 0 ? value : fallbackChannels})`;
}

/** `Candle.time`(ISO 날짜/일시 문자열)을 라이브러리가 요구하는 초 단위 타임스탬프로 바꾼다. */
function toUtcTimestamp(time: string): UTCTimestamp {
  return Math.floor(Date.parse(time) / 1000) as UTCTimestamp;
}

/**
 * `lightweight-charts` 를 import 하는 유일한 파일이다(#242 O6 계약) — 라이브러리 타입은 이
 * 함수의 반환 형태(`CandleChartHandle`) 밖으로 나가지 않는다. 색은 호출 시점의 CSS 변수
 * (`--market-up`·`--market-down`·`--slate-*`·`--ink-muted`)를 읽어 시각 정체성(#242 O3)을
 * 그대로 따른다. `layout.attributionLogo` 는 건드리지 않는다 — 기본값(표시)을 유지한다
 * [Source: 설계 §7 판단 2 권고안].
 */
export function createCandleChart(container: HTMLElement): CandleChartHandle {
  const upColor = readCssColor(container, "--market-up", "240 70 90");
  const downColor = readCssColor(container, "--market-down", "59 130 246");
  const gridColor = readCssColor(container, "--slate-line", "35 42 54");
  const textColor = readCssColor(container, "--ink-muted", "107 118 134");
  const bgColor = readCssColor(container, "--slate-panel", "20 25 34");

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

  const candleSeries: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
    upColor,
    downColor,
    borderUpColor: upColor,
    borderDownColor: downColor,
    wickUpColor: upColor,
    wickDownColor: downColor,
  });

  const volumeSeries: ISeriesApi<"Histogram"> = chart.addSeries(HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
  });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

  const overlays = new Map<string, ISeriesApi<"Line">>();
  let overlayColorIndex = 0;

  return {
    setCandles(candles) {
      candleSeries.setData(
        candles.map((candle) => ({
          time: toUtcTimestamp(candle.time),
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        })),
      );
      volumeSeries.setData(
        candles.map((candle) => ({
          time: toUtcTimestamp(candle.time),
          value: candle.volume,
          color: candle.close >= candle.open ? upColor : downColor,
        })),
      );
    },

    setOverlay(id, points) {
      let series = overlays.get(id);
      if (!series) {
        const color = OVERLAY_PALETTE[overlayColorIndex % OVERLAY_PALETTE.length];
        overlayColorIndex += 1;
        series = chart.addSeries(LineSeries, { color, lineWidth: 1 });
        overlays.set(id, series);
      }
      series.setData(points.map((point) => ({ time: toUtcTimestamp(point.time), value: point.value })));
    },

    removeOverlay(id) {
      const series = overlays.get(id);
      if (!series) return;
      chart.removeSeries(series);
      overlays.delete(id);
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
