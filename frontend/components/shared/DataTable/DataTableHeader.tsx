// components/shared/DataTable/DataTableHeader.tsx
"use client";

import type { CSSProperties } from "react";
import { type HeaderGroup, flexRender } from "@tanstack/react-table";
import type { GridColumn } from "@/types/grid";
import { DataTableFilterRow } from "./DataTableFilterRow";
import {
  COLUMN_RESIZE_STEP_PX,
  type ColumnLayoutMap,
  DEFAULT_MIN_COLUMN_WIDTH,
  STICKY_SHADOW_CLASS,
  type StickyPlacement,
  clampColumnWidth,
} from "./gridColumnLayout";

const ALIGN_CLASS: Record<"left" | "center" | "right", string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

interface DataTableHeaderProps<T> {
  headerGroups: HeaderGroup<T>[];
  columns: GridColumn<T>[];
  showSelectionColumn: boolean;
  selectionMode: "single" | "multiple" | "none";
  allSelected: boolean;
  onToggleAll: (checked: boolean) => void;
  hasFilterableColumn: boolean;
  filter: unknown[] | undefined;
  onFilterChange: (filter: unknown[] | undefined) => void;
  columnLayout: ColumnLayoutMap;
  onColumnResize: (columnId: string, size: number) => void;
}

function stickyCellStyle(placement: StickyPlacement | undefined): CSSProperties {
  if (!placement) return {};
  return {
    position: "sticky",
    [placement.position]: placement.offset,
    zIndex: 20,
  };
}

export function DataTableHeader<T>({
  headerGroups,
  columns,
  showSelectionColumn,
  selectionMode,
  allSelected,
  onToggleAll,
  hasFilterableColumn,
  filter,
  onFilterChange,
  columnLayout,
  onColumnResize,
}: DataTableHeaderProps<T>) {
  return (
    <thead className="sticky top-0 z-10 bg-gray-50">
      {headerGroups.map((headerGroup) => (
        <tr key={headerGroup.id} className="border-b" aria-rowindex={1}>
          {showSelectionColumn && (
            <th scope="col" className="w-8 border-b bg-gray-50 px-2 py-1.5">
              {selectionMode === "multiple" && (
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(event) => onToggleAll(event.target.checked)}
                  aria-label="전체 선택"
                />
              )}
            </th>
          )}
          {headerGroup.headers.map((header) => {
            const column = columns.find((col) => col.field === header.column.id);
            const align = column?.align ?? "left";
            const sorted = header.column.getIsSorted();
            const layout = columnLayout[header.column.id];
            const sticky = layout?.sticky;
            const minWidth = column?.minWidth ?? DEFAULT_MIN_COLUMN_WIDTH;
            const currentSize = layout?.width ?? header.column.getSize();

            return (
              <th
                key={header.id}
                scope="col"
                className={`relative border-b px-2 py-1.5 font-medium text-gray-700 ${ALIGN_CLASS[align]} ${
                  sticky ? `bg-gray-50 ${sticky.isBoundary ? STICKY_SHADOW_CLASS[sticky.position] : ""}` : ""
                }`}
                style={{ width: currentSize, ...stickyCellStyle(sticky) }}
              >
                {header.column.getCanSort() ? (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-blue-600"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    <span aria-hidden="true">{sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}</span>
                  </button>
                ) : (
                  flexRender(header.column.columnDef.header, header.getContext())
                )}

                {header.column.getCanResize() && (
                  // WAI-ARIA "Window Splitter" 패턴 — 마우스 드래그(getResizeHandler)와
                  // 화살표 키 둘 다 같은 폭 상태를 바꾼다. 마우스 전용 상호작용을 만들지
                  // 않는다는 오더 요구가 이 role="separator" + onKeyDown 조합의 근거다.
                  <div
                    role="separator"
                    aria-orientation="vertical"
                    aria-label={`${column?.caption ?? header.column.id} 열 너비 조절`}
                    aria-valuenow={Math.round(currentSize)}
                    aria-valuemin={minWidth}
                    tabIndex={0}
                    onMouseDown={header.getResizeHandler()}
                    onTouchStart={header.getResizeHandler()}
                    onKeyDown={(event) => {
                      if (event.key === "ArrowLeft") {
                        event.preventDefault();
                        onColumnResize(
                          header.column.id,
                          clampColumnWidth(currentSize - COLUMN_RESIZE_STEP_PX, minWidth),
                        );
                      } else if (event.key === "ArrowRight") {
                        event.preventDefault();
                        onColumnResize(
                          header.column.id,
                          clampColumnWidth(currentSize + COLUMN_RESIZE_STEP_PX, minWidth),
                        );
                      }
                    }}
                    className="absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none select-none hover:bg-blue-300 focus-visible:bg-blue-400 focus-visible:outline-none"
                  />
                )}
              </th>
            );
          })}
        </tr>
      ))}
      {hasFilterableColumn && (
        <tr className="border-b bg-gray-50">
          {showSelectionColumn && <td className="px-2 py-1" />}
          <DataTableFilterRow
            columns={columns}
            filter={filter}
            onFilterChange={onFilterChange}
            columnLayout={columnLayout}
          />
        </tr>
      )}
    </thead>
  );
}
