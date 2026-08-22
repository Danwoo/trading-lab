// hooks/shared/useServerTable.ts
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApiErrorMessage } from "@/utils/common/errors";
import { ApiCallFailure } from "@/utils/common/api/client";
import { showToast } from "@/components/shared/Feedback/toastQueue";
import { PAGE_SIZE } from "@/constants/app";
import { applyClientQuery, buildGridQuery } from "@/hooks/shared/gridQuery";
import type { GridQuery, GridSort } from "@/types/grid";

export { buildGridQuery } from "@/hooks/shared/gridQuery";

export interface ServerTableState<T> {
  rows: T[];
  totalCount: number;
  isLoading: boolean;
  /**
   * 마지막 요청이 실패했으면 그 사유, 성공했으면 null. **`rows: []` 하나로는 「못 읽음」과
   * 「정상 0건」이 구별되지 않는다** — 빈 상태 문구를 그리기 전에 이 값을 먼저 봐야 한다.
   * 새 요청이 나가는 순간 null 로 돌아간다(로딩 중에는 지난 실패를 주장하지 않는다).
   */
  error: unknown | null;
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
  const [error, setError] = useState<unknown>(null);
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

  const applyResponse = useCallback((response: { items: T[]; total_count: number } | null) => {
    // `apiCall` 은 `{success:false}` 를 `null` 로 돌려준다 — 격자 경로에서는 그 `null` 을 실패로
    // 읽는다. 여기서 안 가르면 서버가 거절한 것이 「총 0건」으로 화면에 적힌다.
    if (!response) throw new ApiCallFailure();
    setError(null);
    setServerRows(response.items ?? []);
    setServerTotalCount(response.total_count ?? 0);
  }, []);

  const applyFailure = useCallback((cause: unknown) => {
    showToast(getApiErrorMessage(cause), "error");
    // 토스트는 2초 뒤 사라진다 — 사유가 화면에 남으려면 상태로도 들고 있어야 한다.
    // `null`·`undefined` 로 거절된 프로미스도 실패이므로 빈 사유를 만들지 않는다.
    setError(cause ?? new ApiCallFailure());
    setServerRows([]);
    setServerTotalCount(0);
  }, []);

  // 서버 모드 — 페이지·정렬·필터·의존성이 바뀔 때마다 재요청한다.
  useEffect(() => {
    if (clientSide) return;

    const token = ++reloadTokenRef.current;
    setIsLoading(true);
    setError(null);

    fetchGridRef
      .current({ skip: query.skip, take: query.take, filter: query.filter, sort: query.sort })
      .then((response) => {
        if (token !== reloadTokenRef.current) return;
        applyResponse(response);
      })
      .catch((cause: unknown) => {
        if (token !== reloadTokenRef.current) return;
        applyFailure(cause);
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
    setError(null);

    fetchGridRef
      .current({})
      .then((response) => {
        if (token !== reloadTokenRef.current) return;
        applyResponse(response);
      })
      .catch((cause: unknown) => {
        if (token !== reloadTokenRef.current) return;
        applyFailure(cause);
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
    error,
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
