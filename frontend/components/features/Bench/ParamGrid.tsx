"use client";

import { useState } from "react";

import type { GridCellOut, GridOut } from "@/schemas/backtest/backtest";
import { cn } from "@/components/shared/ui/primitives/cn";
import { redactReason } from "@/utils/common/errors/redactReason";

interface Props {
  grid: GridOut;
  selectedRunId: number | null;
  onSelect: (runId: number, label: string) => void;
}

/**
 * 이 칸의 지표를 **성적 척도에 올려도 되는가** (#349).
 *
 * 한 번도 사지 않은 조합은 자산곡선이 시작 자금 그대로 평평하다 — 거기서 나오는
 * 「미회복 0봉 · 낙폭 0% · 수익률 +0.0%」는 성적이 아니라 **아무 일도 없었다**는 뜻이다.
 * 그것을 값으로 칠하면 척도의 **가장 좋은 끝**에 놓여, 격자만 보고 고른 사람이
 * 아무것도 하지 않는 봇을 고른다(실측: 25칸 중 16칸).
 *
 * `absent_reason` 이 실린 칸은 여기서 걸러 색·최댓값 계산 어디에도 들어가지 않는다.
 */
function shadeable(cell: GridCellOut) {
  if (!cell.metrics || absentReasonOf(cell)) return null;
  return cell.metrics;
}

/**
 * 이 칸이 왜 성적을 못 내는가 — **가림을 지난 문구로만** 읽는다.
 *
 * 사유는 화면으로 나가는 값이라 `redactReason` 이 마지막 관문이다(#251). 읽는 자리를
 * 여기 하나로 모아, 판정(척도에서 뺄까)과 표시(뭐라고 적을까)가 같은 문구를 본다.
 */
function absentReasonOf(cell: GridCellOut): string | null {
  return redactReason(cell.metrics?.absent_reason);
}

/** 「몇 건 사고팔았나」 — 「청산 안 함」과 「거래 없음」을 가른다 (#314). */
function tradeNote(metrics: NonNullable<GridCellOut["metrics"]>): string {
  const closed = `청산된 거래 ${metrics.closed_trades}건`;
  return metrics.open_positions > 0 ? `${closed} · 구간 끝에 열린 자리 ${metrics.open_positions}건` : closed;
}

/**
 * 격자를 무엇으로 칠할까 — **기본은 1급 지표다** (#220).
 *
 * 스펙 D-Q2 가 순서를 뒤집어 놨다: *"트레이더가 계좌를 닫는 이유는 샤프가 낮아서가 아니라
 * 낙폭을 못 견뎌서다."* 격자는 **조합을 고르는 자리**라, 여기서 4급(수익률)만 보이면
 * 「가장 많이 번 칸」이 가장 진해 보이고 사용자는 그 칸을 고른다. 리포트에서 1급을 볼
 * 때는 이미 고른 뒤이고, **고른 뒤에 보이는 것은 선택을 못 바꾼다.**
 *
 * 수익률을 지우지는 않는다 — 고를 수 있게 두되 기본이 아니다.
 */
export const GRID_SHADING = {
  longest_underwater: {
    label: "최장 미회복 기간",
    unit: "봉",
    /** 짧을수록 좋다 — 색 강도는 «나쁨»에 비례한다(길수록 진하다). */
    worseIsHigher: true,
    of: (cell: GridCellOut) => shadeable(cell)?.longest_underwater ?? null,
  },
  mdd_pct: {
    label: "최대 낙폭",
    unit: "%",
    worseIsHigher: true,
    of: (cell: GridCellOut) => {
      const mdd = shadeable(cell)?.mdd_pct;
      return mdd === null || mdd === undefined ? null : Math.abs(mdd);
    },
  },
  total_return_pct: {
    label: "구간 총수익률",
    unit: "%",
    worseIsHigher: false,
    of: (cell: GridCellOut) => shadeable(cell)?.total_return_pct ?? null,
  },
} as const;

export type GridShadingKey = keyof typeof GRID_SHADING;

/** 기본 채색 — 1급 지표. 바꾸려면 사용자가 고른다. */
export const DEFAULT_SHADING: GridShadingKey = "longest_underwater";

function cellReturnPct(cell: GridCellOut, initialCash: number): number | null {
  if (cell.final_equity === null || initialCash <= 0) return null;
  return (cell.final_equity / initialCash - 1) * 100;
}

function cellLabel(cell: GridCellOut, axisNames: string[]): string {
  return axisNames.map((name) => `${name}=${String(cell.params[name])}`).join(" · ");
}

/**
 * 한 칸. 등락은 데이터라 데이터색(`--market-up/down`)을 갖고, 강도는 격자 안 최대 수익률
 * 대비 알파로 만든다. **부호를 항상 함께 그린다** — 색맹·흑백 어디서도 뜻이 남아야 한다
 * (디자인 시스템 §2.3).
 */
function Cell({
  cell,
  initialCash,
  maxAbsValue,
  axisNames,
  shading,
  selected,
  onSelect,
}: {
  cell: GridCellOut;
  initialCash: number;
  maxAbsValue: number;
  axisNames: string[];
  shading: GridShadingKey;
  selected: boolean;
  onSelect: (runId: number, label: string) => void;
}) {
  const label = cellLabel(cell, axisNames);
  const spec = GRID_SHADING[shading];
  const value = spec.of(cell);
  const returnPct = cellReturnPct(cell, initialCash);

  // **세 가지를 가른다** — 「실패」·「거래 없음」·「이 지표만 없음」.
  //
  // 매매가 0건이면 「최장 미회복 기간」은 정당하게 없는 값이다. 그것을 실패로 그리면 화면이
  // 사실이 아닌 것을 말하고(FR-021), 0 으로 그리면 **가장 좋은 칸**으로 말한다 (#349).
  // 거래 0건 칸은 척도의 어느 끝도 아니라 **척도 밖**이므로 배경색을 주지 않는다.
  if (cell.status === "failed" || value === null) {
    const failed = cell.status === "failed";
    const absentReason = absentReasonOf(cell);
    const traded = cell.metrics ? cell.metrics.closed_trades + cell.metrics.open_positions : null;
    const shown = failed ? "실패" : absentReason !== null && traded !== null ? `거래 ${traded}건` : "—";
    const why = failed
      ? (redactReason(cell.failed_reason) ?? undefined)
      : absentReason !== null
        ? `${absentReason} — 성적 척도에서 뺐습니다`
        : `${spec.label} 값이 없습니다 — 눌러서 이유를 보세요`;
    return (
      <button
        type="button"
        onClick={() => onSelect(cell.run_id, label)}
        title={why}
        aria-label={`${label} — ${failed ? "실패" : absentReason !== null ? absentReason : `${spec.label} 없음`}`}
        className={cn(
          "min-h-[26px] w-full min-w-0 break-keep rounded-badge px-1 py-0.5 text-2xs tabular-nums",
          failed ? "text-danger" : "text-ink-muted",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
          selected ? "border-2 border-ink-strong" : failed ? "border border-line" : "border border-dashed border-line",
        )}
      >
        {shown}
      </button>
    );
  }

  // 강도는 **나쁨**에 비례한다 — 「가장 진한 칸」이 「가장 조심할 칸」이다.
  // 수익률로 칠할 때만 방향이 뒤집힌다(많이 벌수록 진하다).
  const worst = maxAbsValue > 0 ? Math.abs(value) / maxAbsValue : 0;
  const alpha = 0.08 + 0.34 * worst;

  // 색 채널은 **뜻**을 따른다: 나쁜 축(미회복·낙폭)은 down, 좋은 축(수익률)은 부호대로.
  const channel = spec.worseIsHigher ? "--market-down" : value >= 0 ? "--market-up" : "--market-down";

  const sign = spec.worseIsHigher ? "" : value >= 0 ? "+" : "−";
  const shown = `${sign}${Math.abs(value).toFixed(spec.unit === "봉" ? 0 : 1)}${spec.unit}`;
  // **수익률은 늘 읽어 준다** — 채색 축이 바뀌어도 「얼마 벌었나」를 잃지 않게.
  const returnNote =
    returnPct === null ? "" : ` · 수익률 ${returnPct >= 0 ? "+" : "−"}${Math.abs(returnPct).toFixed(1)}%`;

  // **거래 건수를 늘 함께 읽어 준다** — 「1건으로 낸 성적」과 「25건으로 낸 성적」은
  // 같은 색이어도 같은 근거가 아니다 (#349).
  const trades = cell.metrics ? ` · ${tradeNote(cell.metrics)}` : "";

  return (
    <button
      type="button"
      onClick={() => onSelect(cell.run_id, label)}
      title={`${label} — ${spec.label} ${shown}${returnNote}${trades}`}
      aria-label={`${label} — ${spec.label} ${shown}${returnNote}${trades}${cell.metrics?.still_underwater ? " · 아직 회복 중" : ""}`}
      aria-pressed={selected}
      style={{ backgroundColor: `rgb(var(${channel}) / ${alpha.toFixed(2)})` }}
      className={cn(
        "min-h-[26px] w-full min-w-0 rounded-badge px-1 py-0.5 text-2xs tabular-nums text-ink",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
        selected ? "border-2 border-ink-strong" : "border border-line",
      )}
    >
      {shown}
    </button>
  );
}

/**
 * 파라미터 민감도 격자 (#203, 스펙 D-Q1) — 단일 점이 아니라 지형을 본다.
 *
 * 축은 백엔드가 이름순으로 준다(grid.axes_from_spec). 2축이면 표(행=첫 축, 열=둘째 축),
 * 1축이면 한 줄이다. 칸을 누르면 곡선·낙폭·거래목록이 그 조합으로 바뀐다(전파 규칙).
 *
 * 폭을 고정하지 않는다 — 표가 자리보다 넓어지면 자기 상자 안에서 가로 스크롤한다.
 */
export function ParamGrid({ grid, selectedRunId, onSelect }: Props) {
  const axisNames = grid.axes.map((a) => a.name);
  // 채색 축은 사용자가 고른다 — **기본은 1급 지표**다 (#220).
  const [shading, setShading] = useState<GridShadingKey>(DEFAULT_SHADING);
  const spec = GRID_SHADING[shading];

  const values = grid.cells.map((cell) => spec.of(cell)).filter((v): v is number => v !== null);
  const maxAbsValue = values.length > 0 ? Math.max(...values.map(Math.abs)) : 0;
  // 척도 밖에 둔 칸을 **세어서 말한다** — 몇 칸이 빠졌는지 모르면 격자가 몇 칸으로 판단한
  // 그림인지 알 수 없다 (#349).
  const outOfScale = grid.cells.filter((cell) => absentReasonOf(cell) !== null).length;

  const [rowAxis, colAxis] = grid.axes.length >= 2 ? [grid.axes[0], grid.axes[1]] : [null, grid.axes[0] ?? null];

  const cellAt = (rowIdx: number, colIdx: number): GridCellOut | undefined =>
    rowAxis && colAxis ? grid.cells[rowIdx * colAxis.values.length + colIdx] : grid.cells[colIdx];

  const renderCell = (cell: GridCellOut | undefined) =>
    cell ? (
      <Cell
        cell={cell}
        initialCash={grid.initial_cash}
        maxAbsValue={maxAbsValue}
        axisNames={axisNames}
        shading={shading}
        selected={cell.run_id === selectedRunId}
        onSelect={onSelect}
      />
    ) : null;

  return (
    <div className="min-w-0">
      {/* **무엇으로 칠했는지 적는다** — 색만으로는 어느 지표인지 알 수 없다. */}
      <div className="mb-1 flex min-w-0 flex-wrap items-center gap-1">
        <span className="break-keep text-2xs text-ink-muted">색 기준</span>
        {(Object.keys(GRID_SHADING) as GridShadingKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setShading(key)}
            aria-pressed={key === shading}
            className={cn(
              "rounded-badge px-1.5 py-0.5 text-2xs",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
              key === shading
                ? "border border-ink-strong text-ink-strong"
                : "border border-line text-ink-muted hover:border-line-strong",
            )}
          >
            {GRID_SHADING[key].label}
          </button>
        ))}
      </div>
      <p className="break-keep text-2xs text-ink-muted">
        「{spec.label}」로 칠했습니다 — 진할수록 {spec.worseIsHigher ? "나쁩니다" : "많이 벌었습니다"}. 격자{" "}
        {grid.cells.length}칸 — 훑는 것도 시도라 시도 {grid.attempts_used}회를 썼습니다.
        {outOfScale > 0 && ` 거래가 없던 ${outOfScale}칸은 성적이 아니라 「거래 0건」으로 두어 척도에서 뺐습니다.`}
      </p>

      {/* 3축 이상은 표로 못 편다 — 자르지 않고 목록으로 전부 낸다 */}
      {grid.axes.length > 2 ? (
        <ul className="mt-2 flex max-h-[40svh] flex-col gap-1 overflow-y-auto">
          {grid.cells.map((cell) => (
            <li key={cell.run_id} className="flex min-w-0 items-center gap-2">
              {renderCell(cell)}
              <span className="min-w-0 break-keep text-2xs text-ink-muted">{cellLabel(cell, axisNames)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-separate border-spacing-0.5">
            <caption className="sr-only">파라미터 조합별 수익률 격자</caption>
            <thead>
              <tr>
                {rowAxis && (
                  <th scope="col" className="break-keep px-1 text-left text-2xs font-ui text-ink-muted">
                    {rowAxis.name} ＼ {colAxis?.name}
                  </th>
                )}
                {colAxis?.values.map((value) => (
                  <th
                    key={String(value)}
                    scope="col"
                    className="px-1 text-right text-2xs font-ui tabular-nums text-ink-muted"
                  >
                    {String(value)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(rowAxis ? rowAxis.values : [null]).map((rowValue, rowIdx) => (
                <tr key={String(rowValue)}>
                  {rowAxis && (
                    <th scope="row" className="px-1 text-left text-2xs font-ui tabular-nums text-ink-muted">
                      {String(rowValue)}
                    </th>
                  )}
                  {colAxis?.values.map((_, colIdx) => (
                    <td key={colIdx} className="p-0">
                      {renderCell(cellAt(rowIdx, colIdx))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
