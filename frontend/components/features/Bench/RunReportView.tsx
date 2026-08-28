"use client";

import { useEffect, useRef } from "react";
import { createEquityChart, type EquityChartHandle, type EquityChartPoint } from "@/lib/bench/equityChart";
import { downsampleLttb, drawdownRatios } from "@/lib/bench/equityMath";
import type {
  ExecutionAssumptionsOut,
  MetricOut,
  OpenPositionOut,
  RunReportOut,
  RunSummaryOut,
  TradeOut,
} from "@/schemas/backtest/backtest";
import { cn } from "@/components/shared/ui/primitives/cn";
import { redactReason } from "@/utils/common/errors/redactReason";

/**
 * 원 단위 정수로 반올림 — 0.5 는 0 에서 먼 쪽으로(−4,123.5 → −4,124). `Math.round` 는 음수의
 * 반을 0 쪽으로 올려 부호에 따라 규칙이 갈린다.
 */
function roundWon(value: number): number {
  return Math.sign(value) * Math.round(Math.abs(value));
}

/**
 * 부호 붙은 원화 — 부호를 항상 함께 그린다 (디자인 시스템 §2.3).
 *
 * 정수다. 체결은 1주 단위인데 비용이 비율이라 실현손익에 소수가 남고, 그대로 찍으면 한 표 안에서
 * `+1,810,707.32` 와 `+281,622` 가 섞인다 — 평가액(`won`)과 같은 규칙으로 맞춘다.
 */
function SignedWon({ value }: { value: number }) {
  const whole = roundWon(value);
  const negative = whole < 0;
  return (
    <span className={cn("tabular-nums", negative ? "text-market-down" : "text-market-up")}>
      {negative ? "−" : "+"}
      {Math.abs(whole).toLocaleString("ko-KR")}
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
              <span className="break-keep text-sm text-ink-muted">{redactReason(metric.absent_reason)}</span>
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

/** 원 단위 정수 표기 — 소수점은 평가액에서 읽을 것이 없다. */
function won(value: number): string {
  return roundWon(value).toLocaleString("ko-KR");
}

/**
 * **구간 끝에 열린 자리** — 「거래 0건인데 +268%」의 정체를 화면이 문장으로 말하는 자리 (#314).
 *
 * 엔진은 구간 끝의 자리를 청산하지 않는다(청산한 척하면 없는 거래를 만든 것이다). 그래서
 * 거래 목록·승률은 「없음」이라 답하는데 자산곡선의 마지막 점은 그 자리의 평가액을 담는다.
 * 두 사실을 나란히 놓고 아무 말도 안 하면 어느 쪽이 거짓인지 화면 안에서 가릴 수 없다.
 */
function OpenPositionNotice({ position }: { position: OpenPositionOut }) {
  return (
    <section
      aria-label="구간 끝에 열린 자리"
      className="min-w-0 border border-hairline p-2"
      // 판정을 뒤집는 사실이라 지표보다 먼저 읽혀야 한다 — 경고가 아니라 사실 고지다.
    >
      <p className="break-keep text-sm text-ink">
        구간 끝에 열린 자리 {position.count}건 — {position.entry_ts ?? "진입일 미기록"} 진입, 평가액{" "}
        <span className="tabular-nums">{won(position.value)}</span>원. 아직 팔지 않았습니다.
      </p>
      <p className="mt-1 break-keep text-2xs text-ink-muted">
        {position.unrealized_share_pct === null
          ? (redactReason(position.absent_reason) ?? "미실현 비중을 낼 수 없습니다.")
          : `이 성과의 ${position.unrealized_share_pct.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}% 가 아직 안 판 자리의 평가액입니다 — 매도 비용은 아직 안 물렸습니다.`}
      </p>
      <p className="mt-0.5 break-keep text-2xs text-ink-muted">유도: {position.derived_from}</p>
    </section>
  );
}

function TradeList({ trades, openPosition }: { trades: TradeOut[]; openPosition: OpenPositionOut | null }) {
  if (trades.length === 0) {
    // **「청산 안 함」과 「거래 없음」은 다른 상태다.** 자리가 열린 채 끝났는데 진입 기록이 남지
    // 않은 옛 실행이 여기로 온다 — 「진입도 없었습니다」로 뭉개면 거짓말이 된다.
    return openPosition ? (
      <p className="break-keep text-sm text-ink">
        청산된 거래 없음 — 구간 끝에 열린 자리 {openPosition.count}건이 있습니다.{" "}
        {redactReason(openPosition.absent_reason) ?? "진입 기록이 이 목록에 없습니다."}
      </p>
    ) : (
      <p className="break-keep text-sm text-ink">거래 없음 — 이 조합에서는 청산은커녕 진입도 없었습니다.</p>
    );
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
                  <SignedWon value={trade.realized_pnl} />
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
 * **이 성과가 무엇을 치르고 남은 것인가** — 비용 미반영 세계와 나란히 (SC-007).
 *
 * 나눗셈이 아니라 **다시 돌린 결과**다. 판정 신호는 두 세계가 같지만(전략은 현금을 안 본다)
 * 비용이 현금을 깎아 **체결 수량**이 달라지므로, 끝난 자산은 나눗셈으로 복원되지 않는다.
 */
function CostComparison({
  run,
  finalEquity,
}: {
  run: RunSummaryOut;
  /** 이 실행이 실제로 끝낸 자산 — 자산곡선의 마지막 점. 없으면 그릴 것이 없다. */
  finalEquity: number | null;
}) {
  const twin = run.costless_summary;

  // 견줄 상대가 없는 이유가 셋이다 — 뭉개면 **터진 실행에 소용없는 재실행을 시킨다.**
  const missing =
    twin === null
      ? run.status === "running" || run.status === "queued"
        ? "실행이 끝나면 채워집니다."
        : "대조군을 돌리지 않은 옛 실행입니다. 다시 실행하면 채워집니다."
      : (redactReason(twin.absent_reason) ?? null);
  if (missing !== null || twin === null) {
    return <p className="break-keep text-2xs text-ink-muted">비용 미반영 대비 — {missing}</p>;
  }
  if (finalEquity === null) {
    return <p className="break-keep text-2xs text-ink-muted">비용 미반영 대비 — 자산곡선이 없어 견줄 수 없습니다.</p>;
  }

  const twinEquity = twin.final_equity as number;
  return (
    <table className="min-w-0 text-2xs">
      <caption className="break-keep pb-1 text-left text-2xs text-ink-muted">
        비용 미반영 대비 — 같은 조합을 비용 0으로 다시 돌린 결과입니다 (시작 자금 {won(run.initial_cash)}원)
      </caption>
      <thead>
        <tr className="text-ink-muted">
          <th scope="col" className="pr-3 text-left font-normal" />
          <th scope="col" className="pr-3 text-right font-normal">
            반영
          </th>
          <th scope="col" className="text-right font-normal">
            미반영
          </th>
        </tr>
      </thead>
      <tbody className="text-ink">
        <tr>
          <th scope="row" className="pr-3 text-left font-normal text-ink-muted">
            끝난 자산
          </th>
          <td className="pr-3 text-right tabular-nums">{won(finalEquity)}</td>
          <td className="text-right tabular-nums">{won(twinEquity)}</td>
        </tr>
        <tr>
          <th scope="row" className="pr-3 text-left font-normal text-ink-muted">
            차이
          </th>
          <td className="pr-3 text-right tabular-nums text-ink-muted">—</td>
          <td className="text-right tabular-nums">{won(twinEquity - finalEquity)}</td>
        </tr>
      </tbody>
    </table>
  );
}

/**
 * **체결 가정** — 비용 가정 바로 아래에 선다 (#313).
 *
 * 비용 3종만 밝히던 화면은 「이 셋만 가정했구나」로 읽혔다. 결과를 더 크게 흔드는 것은
 * 체결 단위(1주냐 소수점이냐)·체결가·유동성 상한이고, **시작 자금은 1주 단위에서 비로소
 * 판정에 참여한다** — 그래서 이 자리에 함께 선다.
 *
 * 한 줄로 이으면 항목 사이 구분점과 항목 안의 구분점이 섞여 어디서 끊기는지 안 보인다
 * (372px 패널에서 실측) — 그래서 항목마다 한 줄이다.
 */
function ExecutionAssumptions({
  assumptions,
  initialCash,
}: {
  assumptions: ExecutionAssumptionsOut;
  initialCash: number;
}) {
  const rows: [string, string][] = [
    ["시작 자금", `${Math.round(initialCash).toLocaleString("ko-KR")}원`],
    ["주문 단위", assumptions.order_unit],
    ["체결가", assumptions.fill_price],
    ["유동성 상한", assumptions.liquidity_cap],
    ["조정 정책", assumptions.adj_policy],
  ];

  return (
    <section aria-label="체결 가정" className="min-w-0">
      <p className="break-keep text-2xs text-ink-muted">체결 가정</p>
      <dl className="min-w-0">
        {rows.map(([label, value]) => (
          <div key={label} className="flex min-w-0 flex-wrap gap-x-1.5 text-2xs text-ink-muted">
            <dt className="shrink-0">{label}</dt>
            <dd className="min-w-0 break-keep text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      {assumptions.stale_reason && (
        <p className="mt-1 break-keep border border-hairline p-2 text-2xs text-ink" role="note">
          {assumptions.stale_reason}
        </p>
      )}
    </section>
  );
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

      <ExecutionAssumptions assumptions={report.execution_assumptions} initialCash={run.initial_cash} />

      {run.status === "failed" ? (
        <p className="break-keep border border-danger p-2 text-sm text-ink" role="alert">
          이 조합은 실패했습니다 — {redactReason(run.failed_reason) ?? "사유가 남지 않았습니다"}
        </p>
      ) : (
        <>
          {report.equity.length === 0 ? (
            <p className="break-keep text-sm text-ink">자산곡선이 없습니다 — 이 실행이 남긴 곡선 행이 0건입니다.</p>
          ) : (
            <EquityCurve report={report} />
          )}

          {report.open_position && <OpenPositionNotice position={report.open_position} />}

          <section aria-label="판정 지표" className="min-w-0">
            <h3 className="break-keep text-sm font-ui text-ink-strong">판정 지표</h3>
            <MetricsList metrics={report.metrics} />
            <div className="mt-2 min-w-0 overflow-x-auto">
              <CostComparison
                run={run}
                finalEquity={report.equity.length > 0 ? report.equity[report.equity.length - 1].equity : null}
              />
            </div>
            <p className="mt-1 break-keep text-2xs text-ink-muted">
              샤프는 무위험수익률 0 가정의 참고용입니다 — 순서가 곧 판정 순서입니다 (낙폭이 먼저).
            </p>
          </section>

          <section aria-label="거래 목록" className="min-w-0">
            <h3 className="break-keep text-sm font-ui text-ink-strong">거래 목록</h3>
            <TradeList trades={report.trades} openPosition={report.open_position} />
          </section>
        </>
      )}
    </div>
  );
}
