// components/features/Common/System/AdminUser/AdminUserAuthorGrid.tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { SelectBox } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { selectUserAuthors, addUserAuthor, removeUserAuthor } from "@/services/common/adminUserService";
import { selectAuthorOptions } from "@/services/common/authorService";
import { AuthorOptionOut } from "@/schemas/common/author";

interface Props {
  email: string;
  height?: string;
  editable?: boolean;
}

interface AuthorRow {
  author_id: string;
  author_nm: string;
}

const AdminUserAuthorGrid: React.FC<Props> = ({ email, height = "250px", editable = true }) => {
  const [authorOptions, setAuthorOptions] = useState<AuthorOptionOut[]>([]);
  const [assignedIds, setAssignedIds] = useState<string[]>([]);

  // 이미 부여된 권한 ID (드롭다운에서 제외 + 부여/회수 후 갱신)
  const loadAssigned = useCallback(async () => {
    const res = await selectUserAuthors(email);
    setAssignedIds((res?.items ?? []).map((a) => a.author_id));
  }, [email]);

  useEffect(() => {
    selectAuthorOptions().then((res) => {
      if (res?.items) setAuthorOptions(res.items);
    });
  }, []);

  useEffect(() => {
    loadAssigned();
  }, [loadAssigned]);

  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "author_id", caption: "권한ID", width: 150 },
    { dataField: "author_nm", caption: "권한명", minWidth: 150 },
  ];

  // 아직 부여되지 않은 권한만 추가 후보로 노출 ("권한코드 : 이름" 라벨)
  const availableOptions = authorOptions
    .filter((o) => !assignedIds.includes(o.author_id))
    .map((o) => ({ ...o, label: `${o.author_id} : ${o.author_nm}` }));

  return (
    <DetailGridPanel
      key={email}
      fetchGrid={async () => selectUserAuthors(email)}
      columns={GRID_COLUMNS}
      keyField="author_id"
      showPaging={false}
      clientSidePaging={true}
      editable={editable}
      height={height}
      apiService={{
        create: async (data: AuthorRow) => {
          await addUserAuthor(email, data.author_id);
          await loadAssigned();
        },
        delete: async (data: AuthorRow) => {
          await removeUserAuthor(email, data.author_id);
          await loadAssigned();
        },
      }}
      FormComponent={(props: any) => <FormComponent {...props} authorOptions={availableOptions} />}
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

export default React.memo(AdminUserAuthorGrid);
