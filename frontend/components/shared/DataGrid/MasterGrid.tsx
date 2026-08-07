// components/shared/DataGrid/MasterGrid.tsx
"use client";

import React, { memo, useCallback, useMemo } from "react";
import { DataTable } from "@/components/shared/DataTable";
import { toGridColumns } from "./legacyColumns";
import type { LegacyGridColumn } from "@/types/grid";
import type { LegacyGridSource } from "@/hooks/shared/legacyGridSource";

interface Props<T> {
  /** `useMasterGridData()` 가 돌려주는 그리드 커널 상태. */
  dataSource: LegacyGridSource<T>;
  columns: LegacyGridColumn[];
  height?: string;
  selectedData?: T | null;
  onSelectionChanged?: (selectedData: T) => void;
}

/**
 * 마스터(좌측 목록) 그리드 — #341 로 DevExtreme `DataGrid` 에서 `DataTable` 커널로 이관됐다.
 *
 * 화면이 넘기는 props(`dataSource`·`columns`·`selectedData`·`onSelectionChanged`)는 그대로다.
 * 페이징·정렬·필터·컬럼 고정·가상 스크롤은 전부 커널이 갖고 있어 여기서는 **선택 모델만**
 * 다룬다.
 *
 * 선택은 체크박스가 아니라 **행 클릭**이다(`selectionMode="none"` + `onRowClick`) — 이관 전
 * `focusedRowEnabled` 단일 선택과 같은 조작감이고, 체크박스 열이 하나 더 생기지 않는다
 * (`WatchlistContainer` 가 먼저 쓴 방식과 같다).
 *
 * 이관 전에 있었으나 **호출부가 0건이라 옮기지 않은 것**: `selectionMode="multiple"` ·
 * `selectAllMode` · `showCheckBoxesMode` · `cellVerticalAlign` · `useGrouping` · `useSummary` ·
 * `clientSidePaging`(이제 `useMasterGridData({ paginate })` 가 정한다) · 그리드 인스턴스 ref
 * (엑셀 내보내기가 더 이상 위젯 인스턴스를 필요로 하지 않는다).
 */
function MasterGridComponent<T>({ dataSource, columns, height = "100%", selectedData, onSelectionChanged }: Props<T>) {
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

  return (
    <DataTable<T>
      table={dataSource}
      columns={gridColumns}
      keyField={keyField}
      height={height}
      selectionMode="none"
      selectedKeys={selectedKeys}
      onRowClick={handleRowClick}
    />
  );
}

export const MasterGrid = memo(MasterGridComponent) as <T>(props: Props<T>) => React.ReactElement;
