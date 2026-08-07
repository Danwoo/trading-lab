// components/features/Common/System/Workspace/WorkspaceUserGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { selectWorkspaceUsers } from "@/services/common/workspaceService";

interface Props {
  workspaceId: number;
  height?: string;
}

const GRID_COLUMNS: LegacyGridColumn[] = [
  { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
  { dataField: "email", caption: "이메일", width: 280 },
  { dataField: "name", caption: "이름", width: 120 },
  { dataField: "dept", caption: "부서", width: 140 },
  { dataField: "author_nm", caption: "권한", minWidth: 150, allowFiltering: false, allowSorting: false },
  {
    dataField: "appr_at",
    caption: "승인",
    width: 90,
    lookup: {
      dataSource: [
        { value: "Y", text: "승인" },
        { value: "N", text: "대기" },
        { value: "R", text: "거부" },
      ],
      displayExpr: "text",
      valueExpr: "value",
    },
  },
  {
    dataField: "use_at",
    caption: "사용",
    width: 90,
    lookup: {
      dataSource: [
        { value: "Y", text: "활성" },
        { value: "N", text: "비활성" },
      ],
      displayExpr: "text",
      valueExpr: "value",
    },
  },
  { dataField: "reg_dt", caption: "가입일시", width: 160, dataType: "datetime" },
];

const WorkspaceUserGrid: React.FC<Props> = ({ workspaceId, height = "100%" }) => {
  return (
    <DetailGridPanel
      key={workspaceId}
      fetchGrid={async (params: any) => selectWorkspaceUsers({ ...params, workspace_id: workspaceId })}
      columns={GRID_COLUMNS}
      keyField="email"
      editable={false}
      height={height}
    />
  );
};

export default React.memo(WorkspaceUserGrid);
