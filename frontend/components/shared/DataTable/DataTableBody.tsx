// components/shared/DataTable/DataTableBody.tsx
"use client";

import type { CSSProperties } from "react";
import { type Row, flexRender } from "@tanstack/react-table";
import type { VirtualItem } from "@tanstack/react-virtual";
import type { GridColumn } from "@/types/grid";
import { type ColumnLayoutMap, STICKY_SHADOW_CLASS, type StickyPlacement } from "./gridColumnLayout";

const ALIGN_CLASS: Record<"left" | "center" | "right", string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

interface DataTableBodyProps<T> {
  columns: GridColumn<T>[];
  rows: Row<T>[];
  isLoading: boolean;
  isEmpty: boolean;
  emptyText: string;
  showSelectionColumn: boolean;
  selectionMode: "single" | "multiple" | "none";
  rowKeyOf: (row: T) => string | number;
  selectedKeySet: Set<string>;
  onToggleRow: (key: string | number, row: T, checked: boolean) => void;
  onRowClick?: (row: T) => void;
  onRowDoubleClick?: (row: T) => void;
  /** 행마다 덧붙일 클래스 (레거시 `inactiveExpr` — DataTable.tsx 의 같은 prop 주석 참조). */
  rowClassName?: (row: T) => string | undefined;
  columnLayout: ColumnLayoutMap;
  /** 가상 스크롤 — 실제로 DOM 에 그릴 행만 담긴다. `rows` 전체가 아니라 이 목록만 순회한다. */
  virtualRows: VirtualItem[];
  paddingTop: number;
  paddingBottom: number;
  /** `<tr>` 실측 높이를 가상화 엔진에 보고한다(ResizeObserver 기반, 초기 추정값을 덮어쓴다). */
  measureRowElement: (node: Element | null) => void;
}

function stickyCellStyle(placement: StickyPlacement | undefined, isSelected: boolean): CSSProperties {
  if (!placement) return {};
  return {
    position: "sticky",
    [placement.position]: placement.offset,
    zIndex: 10,
    // sticky td 는 옆으로 스크롤되는 다른 셀이 그 아래로 지나가므로, 배경이 투명하면 겹쳐
    // 보인다 — 행의 현재 상태(선택됨/기본)와 같은 불투명 배경을 이 셀에도 직접 줘야 한다.
    // #eff6ff 는 Tailwind 기본 팔레트 blue-50 (bg-blue-50 이 렌더하는 값과 동일) — group-hover
    // 클래스가 hover 시 이 색으로 덮어쓴다.
    backgroundColor: isSelected ? "#eff6ff" : "#ffffff",
  };
}

export function DataTableBody<T>({
  columns,
  rows,
  isLoading,
  isEmpty,
  emptyText,
  showSelectionColumn,
  selectionMode,
  rowKeyOf,
  selectedKeySet,
  onToggleRow,
  onRowClick,
  onRowDoubleClick,
  rowClassName,
  columnLayout,
  virtualRows,
  paddingTop,
  paddingBottom,
  measureRowElement,
}: DataTableBodyProps<T>) {
  if (isLoading && isEmpty) {
    return (
      <tbody>
        {Array.from({ length: 5 }).map((_, index) => (
          <tr key={`skeleton-${index}`} className="border-b">
            {showSelectionColumn && <td className="px-2 py-2" />}
            {columns.map((col) => (
              <td key={col.field} className="px-2 py-2">
                <div className="h-3 animate-pulse rounded bg-gray-200" />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    );
  }

  if (isEmpty) {
    return (
      <tbody>
        <tr>
          <td
            colSpan={columns.length + (showSelectionColumn ? 1 : 0)}
            role="status"
            className="px-2 py-12 text-center text-gray-500"
          >
            {emptyText}
          </td>
        </tr>
      </tbody>
    );
  }

  return (
    <tbody>
      {paddingTop > 0 && (
        <tr aria-hidden="true">
          <td
            style={{ height: paddingTop, padding: 0, border: 0 }}
            colSpan={columns.length + (showSelectionColumn ? 1 : 0)}
          />
        </tr>
      )}
      {virtualRows.map((virtualRow) => {
        const row = rows[virtualRow.index];
        if (!row) return null;
        const key = rowKeyOf(row.original);
        const isSelected = selectedKeySet.has(String(key));

        return (
          <tr
            key={row.id}
            ref={measureRowElement}
            data-index={virtualRow.index}
            // 헤더는 항상 aria-rowindex=1 이라 데이터 행은 2부터 시작한다. virtualRow.index 는
            // DOM 에 없는 행을 건너뛰어도 실제 논리적 위치를 그대로 담고 있다 — 이 값이
            // "화면에 3개만 그렸다고 3행짜리 표로 읽히는" 문제를 막는다.
            aria-rowindex={virtualRow.index + 2}
            className={`group cursor-pointer border-b hover:bg-blue-50 ${isSelected ? "bg-blue-50" : ""} ${
              rowClassName?.(row.original) ?? ""
            }`}
            aria-selected={selectionMode !== "none" ? isSelected : undefined}
            onClick={() => {
              if (selectionMode === "single") onToggleRow(key, row.original, !isSelected);
              onRowClick?.(row.original);
            }}
            onDoubleClick={onRowDoubleClick ? () => onRowDoubleClick(row.original) : undefined}
          >
            {showSelectionColumn && (
              <td className="px-2 py-1.5" onClick={(event) => event.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(event) => onToggleRow(key, row.original, event.target.checked)}
                  aria-label={`${String(key)} 행 선택`}
                />
              </td>
            )}
            {row.getVisibleCells().map((cell) => {
              const column = columns.find((col) => col.field === cell.column.id);
              const align = column?.align ?? "left";
              const layout = columnLayout[cell.column.id];
              const sticky = layout?.sticky;
              return (
                <td
                  key={cell.id}
                  className={`px-2 py-1.5 ${ALIGN_CLASS[align]} ${
                    sticky
                      ? `group-hover:bg-blue-50 ${sticky.isBoundary ? STICKY_SHADOW_CLASS[sticky.position] : ""}`
                      : ""
                  }`}
                  style={{ width: layout?.width, ...stickyCellStyle(sticky, isSelected) }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              );
            })}
          </tr>
        );
      })}
      {paddingBottom > 0 && (
        <tr aria-hidden="true">
          <td
            style={{ height: paddingBottom, padding: 0, border: 0 }}
            colSpan={columns.length + (showSelectionColumn ? 1 : 0)}
          />
        </tr>
      )}
    </tbody>
  );
}
