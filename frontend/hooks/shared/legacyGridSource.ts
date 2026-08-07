// hooks/shared/legacyGridSource.ts
//
// 레거시 그리드 세 훅(useMasterGridData·useDetailGridData·useSelectGridData)이 공유하는
// 데이터 원천 (#341).
//
// 이관 전에는 셋 다 DevExtreme `DataSource` + `CustomStore`(또는 `ArrayStore`)를 각자 만들었고,
// 그 객체를 화면이 그리드에 `dataSource` prop 으로 그대로 넘겼다. devextreme 을 걷어내면서
// **그 자리를 `useServerTable`(신규 그리드 커널의 상태 훅)이 대신 채운다** — 화면은 여전히
// `dataSource` 를 받아서 넘기기만 하므로 손대지 않는다.
//
// 서버로 나가는 질의 모양(`{skip, take, filter, sort}`)은 `CustomStore.load(loadOptions)` 가
// 넘기던 것과 같다 — 백엔드 파서는 아무것도 바뀌지 않는다. `rn`(ROW_NUMBER) 정렬 제거도
// `gridQuery.ts` 가 이미 같은 처리를 한다(세 훅이 각자 하던 것을 커널이 흡수).

"use client";

import { useCallback, useMemo } from "react";
import { useServerTable, type ServerTableState } from "@/hooks/shared/useServerTable";

/** 레거시 그리드가 `dataSource` prop 으로 받는 것. 커널 상태 + 전체 조회(엑셀 내보내기용). */
export interface LegacyGridSource<T> extends ServerTableState<T> {
  /** 페이징을 무시하고 현재 필터·정렬 기준 전체 행을 받아온다. */
  fetchAll: () => Promise<T[]>;
  /**
   * 행 키가 되는 필드. **원천이 싣고 다닌다** — 이관 전에는 `CustomStore({ key })` 가 이 값을
   * 갖고 있어서 그리드가 따로 알 필요가 없었다. 그리드 prop 으로 옮기면 화면이 훅과 그리드
   * 양쪽에 같은 값을 적어야 하고, 한쪽만 적으면(실제로 화면 9곳이 훅에만 적었다) 그리드가
   * 다른 키로 행을 식별해 선택 강조가 조용히 어긋난다.
   */
  keyField: string;
}

interface Params<T> {
  fetchGrid: (params?: any) => Promise<{ items: T[]; total_count: number } | null>;
  keyField: string;
  pageSize: number;
  /** false 면 전체를 한 번 받아 로컬에서 페이징·정렬·필터한다(이관 전 `paginate: false`). */
  paginate?: boolean;
  dependencies?: unknown[];
}

export function useLegacyGridSource<T>({
  fetchGrid,
  keyField,
  pageSize,
  paginate = true,
  dependencies = [],
}: Params<T>): LegacyGridSource<T> {
  const table = useServerTable<T>({
    fetchGrid,
    pageSize,
    clientSide: !paginate,
    dependencies,
  });

  // 엑셀 내보내기는 "지금 화면의 한 페이지"가 아니라 전체를 받는다 — 이관 전
  // `exportDataGrid` 도 스토어에서 전체를 다시 읽었다. 필터·정렬은 유지하고 skip/take 만 뺀다.
  const fetchAll = useCallback(async () => {
    const response = await fetchGrid({ filter: table.query.filter, sort: table.query.sort });
    return response?.items ?? [];
  }, [fetchGrid, table.query.filter, table.query.sort]);

  return useMemo(() => ({ ...table, fetchAll, keyField }), [table, fetchAll, keyField]);
}

/**
 * 이미 손에 있는 배열을 그리드 커널 상태로 감싼다 — 서버 왕복이 없는 목록(`DualSelectGrid` 의
 * 좌/우 목록)용. 정렬·필터는 커널이 로컬로 처리한다(`clientSide`).
 */
export function useStaticGridSource<T>(rows: T[], pageSize: number): ServerTableState<T> {
  const fetchGrid = useCallback(async () => ({ items: rows, total_count: rows.length }), [rows]);
  return useServerTable<T>({ fetchGrid, pageSize, clientSide: true, dependencies: [rows] });
}
