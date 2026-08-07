// hooks/shared/useDetailGridData.ts
import { useState, useCallback } from "react";
import { PAGE_SIZE } from "@/constants/app";
import { useLegacyGridSource } from "@/hooks/shared/legacyGridSource";

interface Params<T> {
  fetchGrid: (params?: any) => Promise<{ items: T[]; total_count: number } | null>;
  keyField?: string;
  onDataChanged?: () => void;
  dependencies?: any[];
  /**
   * false 면 전체를 한 번 받아 정렬·필터·페이징을 로컬에서 한다(레거시 `clientSidePaging`).
   * 이 값을 안 넘기면 서버 모드가 되는데, 호출부가 서버로 skip/take 를 안 보내는 화면이면
   * 정렬·필터가 **조용히 아무 일도 하지 않게** 된다 — `DetailGridPanel` 이 그 짝이다.
   */
  paginate?: boolean;
}

/**
 * 디테일 그리드(상세 탭 안 목록)의 데이터 + 선택 상태.
 * `dataSource` 는 #341 이관 이후 그리드 커널 상태다 — `useMasterGridData` 주석 참조.
 *
 * 이관 전에 있던 `onLocalUpdate`(CustomStore.update 로 셀 편집 결과를 가로채는 콜백)는 없앴다 —
 * 호출부 전수 조사에서 이 값을 넘기는 화면이 0건이었고, 셀 인라인 편집을 쓰는 화면도 0건이다
 * (`DetailGridPanel` 의 `editMode` 기본값이 "modal" 이고 다른 값을 넘기는 곳이 없다).
 */
export function useDetailGridData<T>({
  fetchGrid,
  keyField = "rn",
  onDataChanged,
  dependencies = [],
  paginate = true,
}: Params<T>) {
  const [selectedData, setSelectedData] = useState<T | null>(null);

  const dataSource = useLegacyGridSource<T>({
    fetchGrid,
    keyField,
    pageSize: PAGE_SIZE.DETAIL,
    paginate,
    dependencies,
  });

  const refreshGrid = useCallback(() => {
    dataSource.reload();
  }, [dataSource]);

  const handleSelect = useCallback((item: T | null) => {
    setSelectedData(item);
  }, []);

  const handleComplete = useCallback(() => {
    setSelectedData(null);
    dataSource.reload();
    onDataChanged?.();
  }, [dataSource, onDataChanged]);

  return {
    dataSource,
    keyField,
    selectedData,
    handleSelect,
    handleComplete,
    refreshGrid,
  } as const;
}
