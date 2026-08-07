// components/features/Common/System/Workspace/WorkspaceDomainGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { TextBox } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import {
  selectWorkspaceDomainList,
  createWorkspaceDomain,
  deleteWorkspaceDomain,
} from "@/services/common/workspaceService";
import { WorkspaceDomain } from "@/schemas/common/workspace";

interface Props {
  workspaceId: number;
  height?: string;
  editable?: boolean;
}

const WorkspaceDomainGrid: React.FC<Props> = ({ workspaceId, height = "100%", editable = true }) => {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "domain", caption: "도메인" },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
  ];

  return (
    <DetailGridPanel
      fetchGrid={async (params: any) => {
        return await selectWorkspaceDomainList({ ...params, workspace_id: workspaceId });
      }}
      columns={GRID_COLUMNS}
      keyField="domain"
      height={height}
      apiService={{
        create: async (data: WorkspaceDomain) => {
          await createWorkspaceDomain({ ...data, workspace_id: workspaceId });
        },
        delete: async (data: WorkspaceDomain) => {
          await deleteWorkspaceDomain({ ...data, workspace_id: workspaceId });
        },
      }}
      FormComponent={FormComponent}
      editable={editable}
    />
  );
};

const FormComponent: React.FC<{
  formData: Partial<WorkspaceDomain>;
  modalMode: "create" | "edit";
  onFieldChange: (field: string, value: any) => void;
  getFieldProps: (field: string) => any;
}> = ({ formData, modalMode, onFieldChange, getFieldProps }) => {
  return (
    <TableGroup title="도메인 정보">
      <TableRow>
        <TableCell label="도메인" required colSpan={3}>
          <TextBox
            fieldName="domain"
            value={formData.domain}
            readOnly={modalMode === "edit"}
            placeholder="예: example.com"
            onValueChanged={(_field, value) =>
              onFieldChange(
                "domain",
                String(value ?? "")
                  .toLowerCase()
                  .trim(),
              )
            }
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>
    </TableGroup>
  );
};

export default React.memo(WorkspaceDomainGrid);
