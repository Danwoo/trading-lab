// hooks/shared/useMasterGridData.ts
import { useState, useCallback } from "react";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast } from "@/components/shared/Feedback";
import { PAGE_SIZE } from "@/constants/app";
import { useLegacyGridSource } from "@/hooks/shared/legacyGridSource";

interface Params<T> {
  fetchGrid: (params?: any) => Promise<{ items: T[]; total_count: number } | null>;
  keyField?: string;
  fetchData?: (data: T) => Promise<T | null>;
  onDataChanged?: () => void;
  dependencies?: any[];
  paginate?: boolean;
}

/**
 * 마스터 그리드(좌측 목록)의 데이터 + 선택 상태.
 *
 * `dataSource` 는 #341 이관 이후 DevExtreme `DataSource` 가 아니라 그리드 커널 상태
 * (`legacyGridSource`)다 — 화면은 이 값을 `<MasterGrid dataSource={...}>` 로 그대로 넘기기만
 * 하므로 계약은 바뀌지 않았다. `keyField` 는 이제 그리드가 행 키를 읽는 데 쓰인다.
 */
export function useMasterGridData<T>({
  fetchGrid,
  keyField = "rn",
  fetchData,
  onDataChanged,
  dependencies = [],
  paginate = true,
}: Params<T>) {
  const dataSource = useLegacyGridSource<T>({
    fetchGrid,
    keyField,
    pageSize: PAGE_SIZE.MASTER,
    paginate,
    dependencies,
  });

  const [selectedData, setSelectedData] = useState<T | null>(null);
  const [isSelectLoading, setIsSelectLoading] = useState<boolean>(false);

  const refreshGrid = useCallback((): void => {
    dataSource.reload();
  }, [dataSource]);

  const handleSelect = useCallback((data: T | null) => {
    setSelectedData(data);
  }, []);

  const handleCreate = useCallback((): void => {
    setSelectedData(null);
  }, []);

  const handleComplete = useCallback(
    (item: T | null): void => {
      setSelectedData(item);
      onDataChanged?.();
    },
    [onDataChanged],
  );

  const handleRefresh = useCallback(async () => {
    refreshGrid();
    if (selectedData && fetchData) {
      setIsSelectLoading(true);
      try {
        const latest = await fetchData(selectedData);
        handleComplete(latest);
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
        handleComplete(null);
      } finally {
        setIsSelectLoading(false);
      }
    } else {
      setIsSelectLoading(false);
    }
  }, [refreshGrid, selectedData, fetchData, handleComplete]);

  const handleCompleteWithRefresh = useCallback(
    (data: T | null, action?: "create" | "update" | "delete"): void => {
      handleComplete(data);
      if (action) refreshGrid();
    },
    [handleComplete, refreshGrid],
  );

  return {
    dataSource,
    keyField,
    selectedData,
    isSelectLoading,
    handleSelect,
    handleCreate,
    handleComplete,
    handleRefresh,
    handleCompleteWithRefresh,
    refreshGrid,
  } as const;
}
