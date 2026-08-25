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
import { NO_AUTHOR_HOW_EDIT, NO_AUTHOR_HOW_VIEW, NO_AUTHOR_PENDING, NO_AUTHOR_TITLE } from "@/constants/accountAuthor";

interface Props {
  email: string;
  /** `tn_user.appr_at` — 승인 전 계정은 권한이 없는 것이 정상이라 안내 문구가 갈린다 (#355). */
  apprAt?: string;
  height?: string;
  editable?: boolean;
}

interface AuthorRow {
  author_id: string;
  author_nm: string;
}

const AdminUserAuthorGrid: React.FC<Props> = ({ email, apprAt, height = "250px", editable = true }) => {
  const [authorOptions, setAuthorOptions] = useState<AuthorOptionOut[]>([]);
  // `null` 은 아직 못 읽은 상태다 — 빈 배열로 시작하면 읽기 전에 「권한 없음」이 깜빡인다.
  const [assignedIds, setAssignedIds] = useState<string[] | null>(null);

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
    .filter((o) => !(assignedIds ?? []).includes(o.author_id))
    .map((o) => ({ ...o, label: `${o.author_id} : ${o.author_nm}` }));

  // 권한 0건은 빈 격자로 두지 않는다 — 빈 칸은 「아직 안 줬다」와 「줄 수 없다」를 가르지 못한다 (#355).
  // 승인된 계정이면 그대로 두면 안 되는 상태(`--caution`)이고, 승인 전이면 정상이라 이유만 말한다.
  const noAuthor = assignedIds !== null && assignedIds.length === 0;
  const pending = apprAt !== undefined && apprAt !== "Y";

  return (
    <div>
      {noAuthor && (
        <p
          role="status"
          className="mb-2 w-full min-w-0 break-keep rounded-panel border border-line bg-bg-raised px-3 py-2"
        >
          <span className={`block font-ui text-sm ${pending ? "text-ink" : "text-caution"}`}>{NO_AUTHOR_TITLE}</span>
          <span className="mt-1 block text-2xs text-ink-muted">
            {pending ? NO_AUTHOR_PENDING : editable ? NO_AUTHOR_HOW_EDIT : NO_AUTHOR_HOW_VIEW}
          </span>
        </p>
      )}
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
    </div>
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
