"use client";

import { useEffect, useRef } from "react";
import { createEquityChart, type EquityChartHandle, type EquityChartPoint } from "@/lib/bench/equityChart";
import { downsampleLttb, drawdownRatios } from "@/lib/bench/equityMath";
import type { MetricOut, RunReportOut, TradeOut } from "@/schemas/backtest/backtest";
import { cn } from "@/components/shared/ui/primitives/cn";

/** 등락 숫자 하나 — 부호를 항상 함께 그린다 (디자인 시스템 §2.3). */
function SignedPct({ value, unit }: { value: number; unit: string }) {
  const negative = value < 0;
  return (
    <span className={cn("tabular-nums", negative ? "text-market-down" : "text-market-up")}>
      {negative ? "−" : "+"}
      {Math.abs(value).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}
      {unit}
    </span>
  );
}

function formatMetricValue(metric: MetricOut): string {
  const value = metric.value as number;
  const digits = metric.unit === "원" ? 0 : metric.unit === "일" || metric.unit === "봉" ? 0 : 2;
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: digits })}${metric.unit}`;
}

/**
 * 판정 지표 — 순서는 서버(D-Q2)가 정한다: 최장 미회복 기간이 맨 위, 샤프는 참고용으로 뒤.
 * 화면이 다시 정렬하지 않는다.
 *
 * 유도 경로 없는 숫자를 올리지 않는다(§8.5.3) — `derived_from` 이 값 옆에 서고, `value` 가
 * 없으면 0 을 그리는 대신 `absent_reason` 을 그대로 낸다. 거래 0건의 승률이 「0%」가 아니라
 * 「거래 없음 — …」으로 뜨는 것이 이 규칙의 끝이다.
 */
function MetricsList({ metrics }: { metrics: MetricOut[] }) {
  return (
    <dl className="flex min-w-0 flex-col">
      {metrics.map((metric) => (
        <div
          key={metric.key}
          className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-b border-hairline py-1.5 last:border-b-0"
        >
          <dt className="min-w-0">
            <span className="break-keep text-sm text-ink">{metric.label}</span>
            <span className="mt-0.5 block break-keep text-2xs text-ink-muted">유도: {metric.derived_from}</span>
          </dt>
          <dd className="min-w-0 text-right">
            {metric.value === null ? (
              <span className="break-keep text-sm text-ink-muted">{metric.absent_reason}</span>
            ) : (
              <span className="text-sm text-ink tabular-nums">{formatMetricValue(metric)}</span>
            )}
            {metric.note && <span className="ml-1 break-keep text-2xs text-ink-muted">({metric.note})</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function TradeList({ trades }: { trades: TradeOut[] }) {
  if (trades.length === 0) {
    return <p className="break-keep text-sm text-ink">거래 없음 — 이 조합에서는 청산은커녕 진입도 없었습니다.</p>;
  }

  return (
    <div className="max-h-[24svh] overflow-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">거래 목록</caption>
        <thead>
          <tr className="text-left text-2xs font-ui text-ink-muted">
            <th scope="col" className="py-1 pr-2 font-ui">
              진입
            </th>
            <th scope="col" className="py-1 pr-2 font-ui">
              청산
            </th>
            <th scope="col" className="py-1 pr-2 text-right font-ui">
              수량
            </th>
            <th scope="col" className="py-1 pr-2 text-right font-ui">
              진입가
            </th>
            <th scope="col" className="py-1 pr-2 text-right font-ui">
              청산가
            </th>
            <th scope="col" className="py-1 text-right font-ui">
              실현손익
            </th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr key={trade.trade_id} className="border-t border-hairline text-ink">
              <td className="py-1 pr-2 tabular-nums">{trade.entry_ts.slice(0, 10)}</td>
              <td className="py-1 pr-2 tabular-nums">{trade.exit_ts ? trade.exit_ts.slice(0, 10) : "보유 중"}</td>
              <td className="py-1 pr-2 text-right tabular-nums">{trade.qty.toLocaleString("ko-KR")}</td>
              <td className="py-1 pr-2 text-right tabular-nums">{trade.fill_price.toLocaleString("ko-KR")}</td>
              <td className="py-1 pr-2 text-right tabular-nums">
                {trade.exit_price === null ? "—" : trade.exit_price.toLocaleString("ko-KR")}
              </td>
              <td className="py-1 text-right">
                {trade.realized_pnl === null ? (
                  <span className="text-ink-muted">미청산</span>
                ) : (
                  <SignedPct value={trade.realized_pnl} unit="" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 자산·낙폭 곡선 — 원본 점을 다 던지지 않고 픽셀 단위로 다운샘플한다 (스펙 §5, LTTB). */
function EquityCurve({ report }: { report: RunReportOut }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EquityChartHandle | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handle = createEquityChart(container);
    chartRef.current = handle;
    return () => {
      handle.destroy();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const handle = chartRef.current;
    if (!container || !handle) return;

    const points = report.equity.map((row, i) => ({ x: i, y: row.equity }));
    const drawdown = drawdownRatios(report.equity.map((row) => row.equity));
    // 픽셀 단위 다운샘플 — 컨테이너 폭의 2배면 어느 확대에서도 선 모양이 남는다.
    const threshold = Math.max(200, container.clientWidth * 2);
    const toChart = (sampled: { x: number; y: number }[]): EquityChartPoint[] =>
      sampled.map((p) => ({ time: report.equity[p.x].dt, value: p.y }));

    handle.setSeries(
      toChart(downsampleLttb(points, threshold)),
      toChart(
        downsampleLttb(
          drawdown.map((ratio, i) => ({ x: i, y: ratio * 100 })),
          threshold,
        ),
      ),
    );
  }, [report]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => chartRef.current?.resize());
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return <div ref={containerRef} className="h-[30svh] w-full min-w-0" />;
}

/** 비용 항목의 사람 말 — 값 자체는 백엔드가 준 키다. */
const COST_LABEL: Record<string, string> = {
  fee_rate: "수수료",
  slippage_rate: "슬리피지",
  sell_tax_rate: "증권거래세",
};

/**
 * 요율을 백분율로. 소수 셋째 자리에서 반올림하면 극소 요율이 「0.000%」가 되어 **0 과
 * 구분되지 않는다** — 그때만 유효숫자로 물러선다.
 */
function ratePercent(rate: number): string {
  const fixed = (rate * 100).toFixed(3);
  return rate > 0 && Number(fixed) === 0 ? (rate * 100).toPrecision(2) : fixed;
}

/**
 * 격자에서 고른 한 조합의 리포트 (#203) — 곡선·낙폭, 판정 지표, 거래목록이 **그 조합으로**
 * 바뀌는 자리다 (전파 규칙 §2.3).
 */
export function RunReportView({ report }: { report: RunReportOut }) {
  const run = report.run;

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="break-keep text-2xs text-ink-muted">
        시도 #{run.attempt_no} · {run.strategy_key} ·{" "}
        {Object.entries(run.params)
          .map(([key, value]) => `${key}=${String(value)}`)
          .join(" · ")}{" "}
        · {run.period_from} ~ {run.period_to}
      </p>

      {/* **이 화면의 모든 숫자가 이 가정 위에 서 있다.** 가정을 안 보이면 수익률·Calmar·샤프가
          무엇을 전제한 값인지 알 수 없다 (제품 정의 counter-metric — 모든 숫자가 출처 표시를
          유지한다). 실측: 명시 비용 3종만으로 회전에 따라 0.24~20.48p 가 갈린다. */}
      <p className="break-keep text-2xs text-ink-muted">
        비용 가정 —{" "}
        {Object.keys(run.cost_assumptions).length === 0
          ? "기록되지 않았습니다"
          : Object.entries(run.cost_assumptions)
              .map(([key, rate]) => `${COST_LABEL[key] ?? key} ${ratePercent(rate)}%`)
              .join(" · ")}
      </p>

      {run.status === "failed" ? (
        <p className="break-keep border border-danger p-2 text-sm text-ink" role="alert">
          이 조합은 실패했습니다 — {run.failed_reason ?? "사유가 남지 않았습니다"}
        </p>
      ) : (
        <>
          {report.equity.length === 0 ? (
            <p className="break-keep text-sm text-ink">자산곡선이 없습니다 — 이 실행이 남긴 곡선 행이 0건입니다.</p>
          ) : (
            <EquityCurve report={report} />
          )}

          <section aria-label="판정 지표" className="min-w-0">
            <h3 className="break-keep text-sm font-ui text-ink-strong">판정 지표</h3>
            <MetricsList metrics={report.metrics} />
            <p className="mt-1 break-keep text-2xs text-ink-muted">
              샤프는 무위험수익률 0 가정의 참고용입니다 — 순서가 곧 판정 순서입니다 (낙폭이 먼저).
            </p>
          </section>

          <section aria-label="거래 목록" className="min-w-0">
            <h3 className="break-keep text-sm font-ui text-ink-strong">거래 목록</h3>
            <TradeList trades={report.trades} />
          </section>
        </>
      )}
    </div>
  );
}
