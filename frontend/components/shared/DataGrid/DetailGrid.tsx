// components/shared/DataGrid/DetailGrid.tsx
"use client";

import React, { memo, useCallback, useMemo } from "react";
import { DataTable } from "@/components/shared/DataTable";
import { toGridColumns } from "./legacyColumns";
import type { LegacyGridColumn } from "@/types/grid";
import type { LegacyGridSource } from "@/hooks/shared/legacyGridSource";

interface Props<T> {
  /** `useDetailGridData()` 가 돌려주는 그리드 커널 상태. */
  dataSource: LegacyGridSource<T>;
  columns: LegacyGridColumn[];
  showPaging?: boolean;
  height?: string;
  /** 이 필드가 "Y" 가 아닌 행을 흐리게 그린다(사용 안 함 표시). */
  inactiveExpr?: string;
  selectedData?: T | null;
  onSelectionChanged?: (selectedData: T) => void;
  onRowDblClick?: (rowData: T) => void;
}

/**
 * 디테일(상세 탭 안) 그리드 — #341 로 DevExtreme `DataGrid` 에서 `DataTable` 커널로 이관됐다.
 * 마스터 그리드와 선택 모델이 같고 페이지 크기·`inactiveExpr` 만 다르다.
 *
 * 이관 전에 있었으나 **호출부가 0건이라 옮기지 않은 것**: 셀 인라인 편집(`editable`/`editMode`
 * — `DetailGridPanel` 이 항상 모달 편집을 쓴다) · `rowDragging` · 다중 선택 · `useGrouping` ·
 * `useSummary` · `cellVerticalAlign`.
 */
function DetailGridComponent<T>({
  dataSource,
  columns,
  showPaging = true,
  height = "100%",
  inactiveExpr,
  selectedData,
  onSelectionChanged,
  onRowDblClick,
}: Props<T>) {
  // 행 키는 원천이 싣고 온다 — 화면이 훅과 그리드에 따로 적다가 어긋나지 않게(legacyGridSource).
  const keyField = dataSource.keyField;
  const gridColumns = useMemo(() => toGridColumns<T>(columns), [columns]);

  const selectedKeys = useMemo(() => {
    if (!selectedData) return [];
    const key = (selectedData as Record<string, unknown>)[keyField];
    return key === undefined || key === null ? [] : [key as string | number];
  }, [selectedData, keyField]);

  const handleRowClick = useCallback(
    (row: T) => {
      onSelectionChanged?.(row);
    },
    [onSelectionChanged],
  );

  const rowClassName = useCallback(
    (row: T) => (inactiveExpr && (row as Record<string, unknown>)[inactiveExpr] !== "Y" ? "text-gray-400" : undefined),
    [inactiveExpr],
  );

  return (
    <DataTable<T>
      table={dataSource}
      columns={gridColumns}
      keyField={keyField}
      height={height}
      showPager={showPaging}
      selectionMode="none"
      selectedKeys={selectedKeys}
      onRowClick={handleRowClick}
      onRowDoubleClick={onRowDblClick}
      rowClassName={inactiveExpr ? rowClassName : undefined}
    />
  );
}

export const DetailGrid = memo(DetailGridComponent) as <T>(props: Props<T>) => React.ReactElement;
