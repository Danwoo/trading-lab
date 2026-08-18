"use client";

import { useEffect } from "react";
import { useTerminalInterval, useTerminalRange } from "@/hooks/terminal/useTerminalContext";
import { setInterval as setTerminalInterval, setRange } from "@/stores/terminal/contextActions";
import type { CandleInterval } from "@/types/terminal/context";

const INTERVAL_OPTIONS: Array<{ value: CandleInterval; label: string }> = [
  { value: "1m", label: "1분" },
  { value: "5m", label: "5분" },
  { value: "15m", label: "15분" },
  { value: "30m", label: "30분" },
  { value: "60m", label: "60분" },
  { value: "1d", label: "일" },
  { value: "1M", label: "월" },
];

/** 이동평균 토글이 다룰 수 있는 기간 — `ChartPanel` 이 이 값 집합으로만 설정을 검증한다. */
export const MOVING_AVERAGE_PERIODS = [5, 20, 60] as const;

const INTRADAY_INTERVALS = new Set<CandleInterval>(["1m", "5m", "15m", "30m", "60m"]);

/** 기간 피커가 아직 없다(§10 갭) — 주기 전환이 스스로 "이 주기라면 이 정도가 자연스러운 기간"을 채운다. */
function defaultRangeFor(interval: CandleInterval): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  if (INTRADAY_INTERVALS.has(interval)) {
    from.setUTCDate(from.getUTCDate() - 5);
  } else if (interval === "1d") {
    from.setUTCFullYear(from.getUTCFullYear() - 1);
  } else {
    from.setUTCFullYear(from.getUTCFullYear() - 5);
  }
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

export interface ChartToolbarProps {
  activeMovingAverages: number[];
  onToggleMovingAverage: (period: number) => void;
}

/**
 * 차트 컨트롤 — 문맥 스토어에 직접 쓸 수 있는 소수(종목 사이드바·차트 컨트롤·AI 콘솔) 중 하나다
 * (`stores/terminal/contextActions.ts` 주석). 주기 버튼은 문맥의 `interval` 을 바꾸고, 기간이
 * 아직 없으면 주기에 맞는 기본 기간을 함께 채운다 — 그래야 `useLoadedSeries` 가 요청을 낸다.
 * 이동평균 토글은 패널 로컬 설정이라 부모(`ChartPanel`)가 관리하는 콜백을 그대로 받는다.
 */
export function ChartToolbar({ activeMovingAverages, onToggleMovingAverage }: ChartToolbarProps) {
  const interval = useTerminalInterval();
  const range = useTerminalRange();

  useEffect(() => {
    // 마운트 시 기간이 비어 있으면 한 번만 채운다 — 사용자가 주기를 바꿀 때는
    // handleIntervalClick 이 그때그때 갱신한다.
    if (range === null) setRange(defaultRangeFor(interval));
    // interval 은 의도적으로 deps 에서 뺀다 — 마운트 1회 보정 전용 effect.
  }, []);

  const handleIntervalClick = (next: CandleInterval) => {
    setTerminalInterval(next);
    setRange(defaultRangeFor(next));
  };

  return (
    <div className="flex flex-shrink-0 flex-wrap items-center gap-3 border-b border-line px-2 py-1 font-mono text-xs">
      <div className="flex items-center gap-1" role="group" aria-label="주기">
        {INTERVAL_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={interval === option.value}
            onClick={() => handleIntervalClick(option.value)}
            className={
              interval === option.value
                ? "rounded-sm bg-bg-raised px-1.5 py-0.5 text-ink"
                : "rounded-sm px-1.5 py-0.5 text-ink-muted hover:text-ink"
            }
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-1" role="group" aria-label="이동평균">
        {MOVING_AVERAGE_PERIODS.map((period) => {
          const active = activeMovingAverages.includes(period);
          return (
            <button
              key={period}
              type="button"
              aria-pressed={active}
              onClick={() => onToggleMovingAverage(period)}
              className={
                active
                  ? "rounded-sm bg-bg-raised px-1.5 py-0.5 text-ink"
                  : "rounded-sm px-1.5 py-0.5 text-ink-muted hover:text-ink"
              }
            >
              MA{period}
            </button>
          );
        })}
      </div>
    </div>
  );
}
