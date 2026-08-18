"use client";

import type { GridCellOut, GridOut } from "@/schemas/backtest/backtest";
import { cn } from "@/components/shared/ui/primitives/cn";

interface Props {
  grid: GridOut;
  selectedRunId: number | null;
  onSelect: (runId: number, label: string) => void;
}

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
  maxAbsReturn,
  axisNames,
  selected,
  onSelect,
}: {
  cell: GridCellOut;
  initialCash: number;
  maxAbsReturn: number;
  axisNames: string[];
  selected: boolean;
  onSelect: (runId: number, label: string) => void;
}) {
  const label = cellLabel(cell, axisNames);
  const returnPct = cellReturnPct(cell, initialCash);

  if (cell.status === "failed" || returnPct === null) {
    return (
      <button
        type="button"
        onClick={() => onSelect(cell.run_id, label)}
        title={cell.failed_reason ?? undefined}
        aria-label={`${label} — 실패`}
        className={cn(
          "min-h-[26px] w-full min-w-0 break-keep rounded-badge px-1 py-0.5 text-2xs text-danger",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
          selected ? "border-2 border-ink-strong" : "border border-line",
        )}
      >
        실패
      </button>
    );
  }

  const alpha = maxAbsReturn > 0 ? 0.08 + 0.34 * (Math.abs(returnPct) / maxAbsReturn) : 0.08;
  const channel = returnPct >= 0 ? "--market-up" : "--market-down";
  const sign = returnPct >= 0 ? "+" : "−";

  return (
    <button
      type="button"
      onClick={() => onSelect(cell.run_id, label)}
      aria-label={`${label} — 수익률 ${sign}${Math.abs(returnPct).toFixed(1)}%`}
      aria-pressed={selected}
      style={{ backgroundColor: `rgb(var(${channel}) / ${alpha.toFixed(2)})` }}
      className={cn(
        "min-h-[26px] w-full min-w-0 rounded-badge px-1 py-0.5 text-2xs tabular-nums text-ink",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
        selected ? "border-2 border-ink-strong" : "border border-line",
      )}
    >
      {sign}
      {Math.abs(returnPct).toFixed(1)}%
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
  const returns = grid.cells
    .map((cell) => cellReturnPct(cell, grid.initial_cash))
    .filter((v): v is number => v !== null);
  const maxAbsReturn = returns.length > 0 ? Math.max(...returns.map(Math.abs)) : 0;

  const [rowAxis, colAxis] = grid.axes.length >= 2 ? [grid.axes[0], grid.axes[1]] : [null, grid.axes[0] ?? null];

  const cellAt = (rowIdx: number, colIdx: number): GridCellOut | undefined =>
    rowAxis && colAxis ? grid.cells[rowIdx * colAxis.values.length + colIdx] : grid.cells[colIdx];

  const renderCell = (cell: GridCellOut | undefined) =>
    cell ? (
      <Cell
        cell={cell}
        initialCash={grid.initial_cash}
        maxAbsReturn={maxAbsReturn}
        axisNames={axisNames}
        selected={cell.run_id === selectedRunId}
        onSelect={onSelect}
      />
    ) : null;

  return (
    <div className="min-w-0">
      <p className="break-keep text-2xs text-ink-muted">
        격자 {grid.cells.length}칸 — 훑는 것도 시도라 시도 {grid.attempts_used}회를 썼습니다.
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
