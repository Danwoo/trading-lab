// hooks/shared/useMasterGridActions.ts
import { useMemo } from "react";
import type { ActionButton } from "@/components/shared/ui";

/**
 * 마스터 그리드 액션 버튼을 관리하는 커스텀 훅
 */
export function useMasterGridActions({
  onCreate,
  onRefresh,
  onExcelDownload,
  customActions = [],
}: {
  onCreate?: () => void;
  onRefresh?: () => void;
  onExcelDownload?: () => void;
  customActions?: ActionButton[];
}) {
  return useMemo(() => {
    const actions: ActionButton[] = [];

    if (onRefresh) {
      actions.push({
        icon: "refresh",
        type: "normal",
        hint: "새로고침",
        onClick: onRefresh,
        sort: 10,
      });
    }

    if (onExcelDownload) {
      actions.push({
        icon: "exportxlsx",
        type: "normal",
        hint: "엑셀다운로드",
        onClick: onExcelDownload,
        sort: 20,
      });
    }

    if (onCreate) {
      actions.push({
        icon: "plus",
        type: "default",
        hint: "등록",
        onClick: onCreate,
        sort: 30,
      });
    }

    return [...actions, ...customActions].sort((a, b) => (a.sort ?? 100) - (b.sort ?? 100));
  }, [onRefresh, onExcelDownload, onCreate, customActions]);
}
