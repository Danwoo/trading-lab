// components/features/Common/System/Workspace/WorkspaceMenuGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { selectWorkspaceMenus } from "@/services/common/workspaceService";

interface Props {
  workspaceId: number;
  height?: string;
}

const GRID_COLUMNS: LegacyGridColumn[] = [
  { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
  { dataField: "menu_id", caption: "메뉴ID", width: 120 },
  { dataField: "menu_nm", caption: "메뉴명" },
  { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
];

/** 워크스페이스가 부여받은 메뉴 목록 (read-only). 부여/회수는 수정 폼의 DualSelectGrid 에서 수행. */
const WorkspaceMenuGrid: React.FC<Props> = ({ workspaceId, height = "100%" }) => {
  return (
    <DetailGridPanel
      key={`${workspaceId}_menu`}
      fetchGrid={async () => {
        const result = await selectWorkspaceMenus(workspaceId);
        if (!result) return null;
        const items = result.workspaceMenus.map((m, index) => ({
          rn: index + 1,
          menu_id: m.menu_id,
          menu_nm: m.menu?.menu_nm ?? m.menu_id,
          reg_dt: m.reg_dt,
          use_at: m.menu?.use_at ?? null,
        }));
        return { items, total_count: items.length };
      }}
      columns={GRID_COLUMNS}
      keyField="menu_id"
      showPaging={false}
      clientSidePaging={true}
      editable={false}
      inactiveExpr="use_at"
      height={height}
    />
  );
};

export default React.memo(WorkspaceMenuGrid);
