// hooks/shared/useDetailGridActions.ts
import { useMemo } from "react";
import type { ActionButton } from "@/components/shared/ui";

/**
 * 디테일 그리드 액션 버튼을 관리하는 커스텀 훅
 */
export function useDetailGridActions({
  onRefresh,
  onCreate,
  onEdit,
  onDelete,
  selectedData,
  customActions = [],
}: {
  onRefresh?: () => void;
  onCreate?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  selectedData?: any;
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

    if (onCreate) {
      actions.push({
        icon: "plus",
        type: "default",
        hint: "등록",
        onClick: onCreate,
        sort: 20,
      });
    }

    if (onEdit) {
      actions.push({
        icon: "edit",
        type: "default",
        hint: "수정",
        onClick: onEdit,
        disabled: !selectedData,
        sort: 30,
      });
    }

    if (onDelete) {
      actions.push({
        icon: "trash",
        type: "danger",
        hint: "삭제",
        onClick: onDelete,
        disabled: !selectedData,
        sort: 40,
      });
    }

    return [...actions, ...customActions].sort((a, b) => (a.sort ?? 100) - (b.sort ?? 100));
  }, [onRefresh, onCreate, onEdit, onDelete, selectedData, customActions]);
}
