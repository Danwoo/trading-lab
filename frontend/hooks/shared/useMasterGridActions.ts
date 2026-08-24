// hooks/shared/useMasterGridActions.ts
import { useMemo } from "react";
import type { ActionButton } from "@/components/shared/ui";
import { withWriteDeniedHint } from "@/constants/writeAccess";

/**
 * 마스터 그리드 액션 버튼을 관리하는 커스텀 훅
 *
 * `writeGated` 는 역할이 이 목록의 쓰기를 막고 있다는 뜻이다 (#341). 그때 「등록」은 사라지지 않고
 * **비활성**으로 서며 `hint`(title) 에 사유를 잇는다 — `DetailGridPanel` 의 격자 아이콘과 같은
 * 규율이다(있는 기능을 감추면 없는 것으로 읽힌다). 판정은 부르는 쪽(`useWriteAccess`)이 한다.
 */
export function useMasterGridActions({
  onCreate,
  onRefresh,
  onExcelDownload,
  customActions = [],
  writeGated = false,
}: {
  onCreate?: () => void;
  onRefresh?: () => void;
  onExcelDownload?: () => void;
  customActions?: ActionButton[];
  writeGated?: boolean;
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
        hint: writeGated ? withWriteDeniedHint("등록") : "등록",
        disabled: writeGated,
        onClick: onCreate,
        sort: 30,
      });
    }

    return [...actions, ...customActions].sort((a, b) => (a.sort ?? 100) - (b.sort ?? 100));
  }, [onRefresh, onExcelDownload, onCreate, customActions, writeGated]);
}
