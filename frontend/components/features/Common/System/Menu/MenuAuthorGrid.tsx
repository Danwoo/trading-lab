// components/features/Common/System/Menu/MenuAuthorGrid.tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { SelectBox } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { selectMenuAuthors, addMenuAuthor, removeMenuAuthor } from "@/services/common/menuService";
import { selectAuthorOptions } from "@/services/common/authorService";
import { AuthorOptionOut } from "@/schemas/common/author";
import { SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

interface Props {
  menuId: string;
  height?: string;
  editable?: boolean;
}

interface AuthorRow {
  author_id: string;
  author_nm: string;
}

const GRID_COLUMNS: LegacyGridColumn[] = [
  { dataField: "author_id", caption: "권한ID", width: 150 },
  { dataField: "author_nm", caption: "권한명", minWidth: 150 },
];

const MenuAuthorGrid: React.FC<Props> = ({ menuId, height = "250px", editable = false }) => {
  const [authorOptions, setAuthorOptions] = useState<AuthorOptionOut[]>([]);
  const [assignedIds, setAssignedIds] = useState<string[]>([]);

  const loadAssigned = useCallback(async () => {
    const res = await selectMenuAuthors(menuId);
    setAssignedIds((res?.items ?? []).map((a) => a.author_id));
  }, [menuId]);

  useEffect(() => {
    if (!editable) return;
    selectAuthorOptions().then((res) => {
      if (res?.items) setAuthorOptions(res.items);
    });
  }, [editable]);

  useEffect(() => {
    if (!editable) return;
    loadAssigned();
  }, [editable, loadAssigned]);

  // 시스템관리자(admin)는 모든 메뉴 접근 → 후보 제외. 이미 부여된 권한도 제외. ("권한코드 : 이름")
  const availableOptions = authorOptions
    .filter((o) => o.author_id !== SYS_ADMIN_AUTHOR_ID && !assignedIds.includes(o.author_id))
    .map((o) => ({ ...o, label: `${o.author_id} : ${o.author_nm}` }));

  return (
    <DetailGridPanel
      key={menuId}
      fetchGrid={async () => selectMenuAuthors(menuId)}
      columns={GRID_COLUMNS}
      keyField="author_id"
      showPaging={false}
      clientSidePaging={true}
      editable={editable}
      height={height}
      apiService={
        editable
          ? {
              create: async (data: AuthorRow) => {
                await addMenuAuthor(menuId, data.author_id);
                await loadAssigned();
              },
              delete: async (data: AuthorRow) => {
                await removeMenuAuthor(menuId, data.author_id);
                await loadAssigned();
              },
            }
          : undefined
      }
      FormComponent={
        editable ? (props: any) => <FormComponent {...props} authorOptions={availableOptions} /> : undefined
      }
    />
  );
};

const FormComponent: React.FC<{
  formData: Partial<AuthorRow>;
  modalMode: "create" | "edit";
  onFieldChange: (field: string, value: any) => void;
  getFieldProps: (field: string) => any;
  authorOptions: (AuthorOptionOut & { label: string })[];
}> = ({ formData, modalMode, onFieldChange, getFieldProps, authorOptions }) => {
  return (
    <TableGroup title="권한 정보">
      <TableRow>
        <TableCell label="권한" required colSpan={3}>
          <SelectBox
            fieldName="author_id"
            value={formData.author_id}
            items={authorOptions}
            displayExpr="label"
            valueExpr="author_id"
            readOnly={modalMode === "edit"}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>
    </TableGroup>
  );
};

export default React.memo(MenuAuthorGrid);
