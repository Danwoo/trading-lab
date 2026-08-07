// components/shared/DataTable/DataTable.tsx
"use client";

import { useCallback, useMemo, useRef } from "react";
import { type ColumnDef, type SortingState, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { GridColumn, GridSort } from "@/types/grid";
import type { ServerTableState } from "@/hooks/shared/useServerTable";
import { formatDate, formatNumber } from "@/utils/common/formatters";
import { DataTablePager } from "./DataTablePager";
import { DataTableHeader } from "./DataTableHeader";
import { DataTableBody } from "./DataTableBody";
import { type ColumnLayoutMap, computeStickyOffsets } from "./gridColumnLayout";

// 모든 데이터 행이 padding(py-1.5=12px) + text-sm 한 줄(20px) + border-b(1px)로 동일한
// 높이라는 가정의 초기 추정값 — 가상 스크롤 초기 레이아웃에만 쓰고, 실제 렌더된 높이는
// ResizeObserver 기반 `measureElement`(DataTableBody)가 실측해 이 추정을 덮어쓴다.
const ESTIMATED_ROW_HEIGHT_PX = 33;
const VIRTUALIZER_OVERSCAN = 8;

export interface DataTableProps<T> {
  table: ServerTableState<T>;
  columns: GridColumn<T>[];
  keyField?: string;
  height?: string;
  selectionMode?: "single" | "multiple" | "none";
  selectedKeys?: Array<string | number>;
  onSelectionChange?: (keys: Array<string | number>, rows: T[]) => void;
  onRowClick?: (row: T) => void;
  /** 행 더블클릭 — 선택 팝업이 "골라서 닫기"에 쓴다(레거시 `SelectGrid` 계약). */
  onRowDoubleClick?: (row: T) => void;
  emptyText?: string;
  /**
   * 페이저 표시 여부. 상세 탭 안의 작은 목록처럼 전체를 한 화면에 보여주는 그리드는 끈다
   * (레거시 `DetailGrid` 의 `showPaging` 계약 — 화면 7곳이 쓴다).
   *
   * **끄더라도 목록이 한 페이지에 안 들어가면 페이저는 뜬다** — 아래 `isTruncated` 참고.
   * 정말 페이저를 한 번도 안 보이게 하려면 페이지 크기를 목록보다 크게 잡아 애초에 자르지
   * 않게 한다(`DualSelectGrid` 의 `UNPAGED_SIZE`).
   */
  showPager?: boolean;
  /**
   * 행마다 덧붙일 클래스. 비활성 행을 흐리게 표시하는 용도로 쓴다(레거시 `inactiveExpr`).
   * **색만으로 상태를 나타내지 않도록** 호출부가 함께 텍스트 단서를 두는지 확인하라 —
   * 여기서는 그 판단을 강제하지 않는다.
   */
  rowClassName?: (row: T) => string | undefined;
}

function defaultCellValue(value: unknown, dataType: GridColumn<unknown>["dataType"], fractionDigits?: number): string {
  if (value === null || value === undefined || value === "") return "";
  switch (dataType) {
    case "number":
      // 레거시 컬럼의 `format`(`#,##0.##`)에서 온 자릿수가 있으면 그것을 따른다.
      return fractionDigits === undefined
        ? formatNumber(value as number, "number")
        : Number(value).toLocaleString("ko-KR", { maximumFractionDigits: fractionDigits });
    case "date":
      return formatDate(value, "date") ?? String(value);
    case "datetime":
      return formatDate(value, "datetime") ?? String(value);
    default:
      return String(value);
  }
}

function rowKeyOf<T>(row: T, keyField: string): string | number {
  const value = (row as Record<string, unknown>)[keyField];
  return typeof value === "number" ? value : String(value);
}

function toTanStackSorting(sort: GridSort[] | undefined): SortingState {
  return (sort ?? []).map((item) => ({ id: item.selector, desc: item.desc }));
}

function toGridSort(sorting: SortingState): GridSort[] {
  return sorting.map((item) => ({ selector: item.id, desc: item.desc }));
}

export function DataTable<T>({
  table,
  columns,
  keyField = "rn",
  height = "100%",
  selectionMode = "none",
  selectedKeys = [],
  onSelectionChange,
  onRowClick,
  onRowDoubleClick,
  emptyText = "표시할 데이터가 없습니다.",
  showPager = true,
  rowClassName,
}: DataTableProps<T>) {
  const columnDefs = useMemo<ColumnDef<T, unknown>[]>(
    () =>
      columns.map((col) => ({
        id: col.field,
        accessorKey: col.field,
        header: col.caption,
        size: col.width,
        minSize: col.minWidth,
        enableSorting: col.sortable !== false,
        cell: col.render
          ? ({ row }) => col.render!(row.original)
          : ({ getValue }) => defaultCellValue(getValue(), col.dataType, col.fractionDigits),
      })),
    [columns],
  );

  const sorting = useMemo(() => toTanStackSorting(table.query.sort), [table.query.sort]);

  const reactTable = useReactTable({
    data: table.rows,
    columns: columnDefs,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualFiltering: true,
    manualPagination: true,
    enableMultiSort: false,
    enableColumnResizing: true,
    // "onChange" — 드래그 중 실시간으로 폭이 바뀐다("onEnd" 는 손을 뗀 순간에만 반영해
    // 드래그 중 미리보기가 없다). 옆 컬럼·고정 컬럼 오프셋이 같이 따라와야 자연스럽다.
    columnResizeMode: "onChange",
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      table.setSort(toGridSort(next));
    },
    getRowId: (row) => String(rowKeyOf(row, keyField)),
  });

  const selectedKeySet = useMemo(() => new Set(selectedKeys.map(String)), [selectedKeys]);
  const hasFilterableColumn = columns.some((col) => col.filterable !== false);
  const showSelectionColumn = selectionMode !== "none";
  const bodyRows = reactTable.getRowModel().rows;
  const allSelected =
    table.rows.length > 0 && table.rows.every((row) => selectedKeySet.has(String(rowKeyOf(row, keyField))));

  // 컬럼 리사이즈·고정(fixed) 오프셋은 매 렌더 다시 계산한다 — 헤더 배열이 작고(수십 개
  // 이하) 계산이 가벼워, TanStack 의 header 객체 재생성 타이밍에 맞춰 memo 키를 관리하는
  // 것보다 항상-최신을 보장하는 이 편이 버그가 적다.
  const leafHeaders = reactTable.getHeaderGroups().at(-1)?.headers ?? [];
  const columnLayout: ColumnLayoutMap = useMemo(() => {
    const stickyInputs = leafHeaders.map((header) => ({
      field: header.column.id,
      fixed: columns.find((col) => col.field === header.column.id)?.fixed,
      size: header.column.getSize(),
    }));
    const stickyPlacements = computeStickyOffsets(stickyInputs);
    return Object.fromEntries(
      stickyInputs.map((input) => [input.field, { width: input.size, sticky: stickyPlacements[input.field] }]),
    );
    // leafHeaders 는 매 렌더 새 배열이라 의존성에 넣으면 memo 가 무의미해진다 — 실제로
    // 폭에 영향을 주는 값(컬럼 정의·현재 columnSizing 상태)만 의존성으로 쓴다.
  }, [columns, reactTable.getState().columnSizing]);

  // <table> 이 `w-full`(100%)만 걸려 있으면 table-layout:auto 인 브라우저가 컬럼 폭 지정을
  // "선호값"으로만 취급하고 컨테이너에 맞춰 전부 눌러 담는다 — 그러면 총 폭이 뷰포트보다
  // 넓어져도 가로 스크롤 자체가 생기지 않고, 고정 컬럼의 sticky 오프셋은 스크롤이 있어야만
  // 의미가 있으므로 이 기능이 조용히 죽는다. 최소 폭을 명시해 "다 안 들어가면 넘친다"를
  // 강제한다.
  const totalColumnsWidth =
    Object.values(columnLayout).reduce((sum, entry) => sum + entry.width, 0) + (showSelectionColumn ? 32 : 0);

  const handleColumnResize = useCallback(
    (columnId: string, size: number) => {
      reactTable.setColumnSizing((prev) => ({ ...prev, [columnId]: size }));
    },
    [reactTable],
  );

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: bodyRows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => ESTIMATED_ROW_HEIGHT_PX,
    overscan: VIRTUALIZER_OVERSCAN,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualRows.length > 0 ? virtualRows[0].start : 0;
  const paddingBottom =
    virtualRows.length > 0 ? rowVirtualizer.getTotalSize() - virtualRows[virtualRows.length - 1].end : 0;

  const toggleRow = useCallback(
    (key: string | number, row: T, checked: boolean) => {
      if (!onSelectionChange) return;
      if (selectionMode === "single") {
        onSelectionChange(checked ? [key] : [], checked ? [row] : []);
        return;
      }
      const nextKeys = checked
        ? [...selectedKeys.filter((existing) => existing !== key), key]
        : selectedKeys.filter((existing) => existing !== key);
      const nextKeyStrings = nextKeys.map(String);
      const nextRows = bodyRows
        .filter((r) => nextKeyStrings.includes(String(rowKeyOf(r.original, keyField))))
        .map((r) => r.original);
      onSelectionChange(nextKeys, nextRows);
    },
    [onSelectionChange, selectionMode, selectedKeys, bodyRows, keyField],
  );

  const toggleAll = useCallback(
    (checked: boolean) => {
      if (!onSelectionChange) return;
      if (!checked) {
        onSelectionChange([], []);
        return;
      }
      onSelectionChange(
        bodyRows.map((r) => rowKeyOf(r.original, keyField)),
        bodyRows.map((r) => r.original),
      );
    },
    [onSelectionChange, bodyRows, keyField],
  );

  const isEmpty = table.rows.length === 0;

  // 커널은 `showPager` 와 무관하게 항상 페이지 크기로 자른다(서버 모드는 take, clientSide 는
  // applyClientQuery 의 slice). 그래서 페이저를 끈 채 목록이 페이지 크기를 넘기면 그 뒤 행에
  // **도달할 수단이 아예 없어진다** — 에러도 빈 상태도 아니고 그냥 조용히 잘린 목록이라
  // 사용자가 알아챌 방법이 없다. 실제로 디테일 그리드 7곳이 15행에서 끊겨 있었다(PR #417
  // 독립 리뷰). 이관 전 DevExtreme 의 `pager visible: "auto"` 기본값이 하던 일을 여기서 되살린다:
  // **잘리고 있으면 페이저는 무조건 뜬다.** 페이저를 끈다는 것은 "이 목록은 한 화면에 다
  // 들어간다"는 주장이고, 그 주장이 틀린 순간 주장 대신 데이터를 택한다.
  const isTruncated = table.totalCount > table.pageSize;
  const pagerVisible = showPager || isTruncated;
  // 가상 스크롤은 화면에 보이는 행만 DOM 에 둔다 — aria-rowcount 로 전체 행 수(헤더 포함)를
  // 알려야 스크린리더가 "N행짜리 표"를 정확히 읽는다. 아직 최초 응답 전(로딩 중 + 데이터
  // 없음)이면 전체 행 수를 모르므로 ARIA 가 정의한 "미상" 값 -1 을 쓴다.
  const ariaRowCount = table.isLoading && isEmpty ? -1 : bodyRows.length + 1;

  return (
    <div className="flex min-h-0 flex-col border" style={{ height }}>
      <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-auto" aria-busy={table.isLoading}>
        <table
          className="w-full border-collapse text-sm"
          style={{ minWidth: totalColumnsWidth }}
          aria-rowcount={ariaRowCount}
        >
          <DataTableHeader
            headerGroups={reactTable.getHeaderGroups()}
            columns={columns}
            showSelectionColumn={showSelectionColumn}
            selectionMode={selectionMode}
            allSelected={allSelected}
            onToggleAll={toggleAll}
            hasFilterableColumn={hasFilterableColumn}
            filter={table.query.filter}
            onFilterChange={table.setFilter}
            columnLayout={columnLayout}
            onColumnResize={handleColumnResize}
          />
          <DataTableBody
            columns={columns}
            rows={bodyRows}
            isLoading={table.isLoading}
            isEmpty={isEmpty}
            emptyText={emptyText}
            showSelectionColumn={showSelectionColumn}
            selectionMode={selectionMode}
            rowKeyOf={(row) => rowKeyOf(row, keyField)}
            selectedKeySet={selectedKeySet}
            onToggleRow={toggleRow}
            onRowClick={onRowClick}
            onRowDoubleClick={onRowDoubleClick}
            columnLayout={columnLayout}
            virtualRows={virtualRows}
            paddingTop={paddingTop}
            paddingBottom={paddingBottom}
            measureRowElement={rowVirtualizer.measureElement}
            rowClassName={rowClassName}
          />
        </table>
      </div>

      {pagerVisible && (
        <DataTablePager
          pageIndex={table.pageIndex}
          pageSize={table.pageSize}
          totalCount={table.totalCount}
          onPageChange={table.setPage}
          onPageSizeChange={table.setPageSize}
        />
      )}
    </div>
  );
}
