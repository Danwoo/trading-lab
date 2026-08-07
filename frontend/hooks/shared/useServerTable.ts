// hooks/shared/useServerTable.ts
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast } from "@/components/shared/Feedback/toastQueue";
import { PAGE_SIZE } from "@/constants/app";
import { applyClientQuery, buildGridQuery } from "@/hooks/shared/gridQuery";
import type { GridQuery, GridSort } from "@/types/grid";

export { buildGridQuery } from "@/hooks/shared/gridQuery";

export interface ServerTableState<T> {
  rows: T[];
  totalCount: number;
  isLoading: boolean;
  query: GridQuery;
  pageIndex: number;
  pageSize: number;
  setPage: (index: number) => void;
  setPageSize: (size: number) => void;
  setSort: (sort: GridSort[]) => void;
  setFilter: (filter: unknown[] | undefined) => void;
  reload: () => void;
}

interface Params<T> {
  fetchGrid: (params: Record<string, unknown>) => Promise<{ items: T[]; total_count: number } | null>;
  pageSize?: number;
  clientSide?: boolean;
  dependencies?: unknown[];
}

export function useServerTable<T>({
  fetchGrid,
  pageSize: initialPageSize = PAGE_SIZE.MASTER,
  clientSide = false,
  dependencies = [],
}: Params<T>): ServerTableState<T> {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [sort, setSortState] = useState<GridSort[] | undefined>(undefined);
  const [filter, setFilterState] = useState<unknown[] | undefined>(undefined);
  const [serverRows, setServerRows] = useState<T[]>([]);
  const [serverTotalCount, setServerTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);

  const fetchGridRef = useRef(fetchGrid);
  useEffect(() => {
    fetchGridRef.current = fetchGrid;
  });

  const query = useMemo(
    () => buildGridQuery({ pageIndex, pageSize, sort, filter }),
    [pageIndex, pageSize, sort, filter],
  );

  const reloadTokenRef = useRef(0);

  // 서버 모드 — 페이지·정렬·필터·의존성이 바뀔 때마다 재요청한다.
  useEffect(() => {
    if (clientSide) return;

    const token = ++reloadTokenRef.current;
    setIsLoading(true);

    fetchGridRef
      .current({ skip: query.skip, take: query.take, filter: query.filter, sort: query.sort })
      .then((response) => {
        if (token !== reloadTokenRef.current) return;
        setServerRows(response?.items ?? []);
        setServerTotalCount(response?.total_count ?? 0);
      })
      .catch((error: unknown) => {
        if (token !== reloadTokenRef.current) return;
        showToast(getApiErrorMessage(error), "error");
        setServerRows([]);
        setServerTotalCount(0);
      })
      .finally(() => {
        if (token !== reloadTokenRef.current) return;
        setIsLoading(false);
      });
  }, [
    clientSide,
    reloadTick,
    query.skip,
    query.take,
    JSON.stringify(query.filter),
    JSON.stringify(query.sort),
    ...dependencies,
  ]);

  // 클라이언트 모드 — 최초 1회(+dependencies·reload 변경 시) 전체를 받고, 이후 정렬·필터·
  // 페이징은 로컬에서 처리한다(`applyClientQuery`). 서버로는 절대 skip/take/filter/sort 를
  // 보내지 않는다 — 리포지토리가 take 없는 skip 을 무시하므로 여기서 그 형태를 만들면 안 된다.
  useEffect(() => {
    if (!clientSide) return;

    const token = ++reloadTokenRef.current;
    setIsLoading(true);

    fetchGridRef
      .current({})
      .then((response) => {
        if (token !== reloadTokenRef.current) return;
        setServerRows(response?.items ?? []);
        setServerTotalCount(response?.total_count ?? 0);
      })
      .catch((error: unknown) => {
        if (token !== reloadTokenRef.current) return;
        showToast(getApiErrorMessage(error), "error");
        setServerRows([]);
        setServerTotalCount(0);
      })
      .finally(() => {
        if (token !== reloadTokenRef.current) return;
        setIsLoading(false);
      });
  }, [clientSide, reloadTick, ...dependencies]);

  const { rows, totalCount } = useMemo(() => {
    if (!clientSide) return { rows: serverRows, totalCount: serverTotalCount };
    return applyClientQuery(serverRows, query);
  }, [clientSide, serverRows, serverTotalCount, query]);

  const setPage = useCallback((index: number) => setPageIndex(Math.max(0, index)), []);

  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPageIndex(0);
  }, []);

  const setSort = useCallback((next: GridSort[]) => {
    setSortState(next.length > 0 ? next : undefined);
    setPageIndex(0);
  }, []);

  const setFilter = useCallback((next: unknown[] | undefined) => {
    setFilterState(next);
    setPageIndex(0);
  }, []);

  const reload = useCallback(() => setReloadTick((tick) => tick + 1), []);

  return {
    rows,
    totalCount,
    isLoading,
    query,
    pageIndex,
    pageSize,
    setPage,
    setPageSize,
    setSort,
    setFilter,
    reload,
  };
}
