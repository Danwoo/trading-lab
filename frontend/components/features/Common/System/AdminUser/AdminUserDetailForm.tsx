// components/features/Common/System/AdminUser/AdminUserDetailForm.tsx
"use client";

import { useEffect, useState } from "react";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { AdminUser, AdminUserCreate } from "@/schemas/common/adminUser";
import { selectWorkspaceOptions } from "@/services/common/workspaceService";
import { WorkspaceOptionOut } from "@/schemas/common/workspace";
import { useSessionContext } from "@/hooks/shared/useSessionContext";
import { isOEM } from "@/utils/common/edition";
import AdminUserAuthorGrid from "./AdminUserAuthorGrid";
import AdminUserSessionGrid from "./AdminUserSessionGrid";

interface Props {
  isNew: boolean;
  initialData: Partial<AdminUser>;
  onSubmit: (data: AdminUser | AdminUserCreate) => Promise<boolean>;
  onCancel?: () => void;
}

const USE_AT_OPTIONS = [
  { value: "Y", text: "활성" },
  { value: "N", text: "비활성" },
];

const APPR_AT_OPTIONS = [
  { value: "Y", text: "승인" },
  { value: "N", text: "대기" },
  { value: "R", text: "거부" },
];

export default function AdminUserDetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<AdminUserCreate>(initialData);
  const [workspaceOptions, setWorkspaceOptions] = useState<WorkspaceOptionOut[]>([]);
  const { isSysAdmin, workspaceId } = useSessionContext();

  useEffect(() => {
    selectWorkspaceOptions().then((res) => {
      if (res?.items) setWorkspaceOptions(res.items);
    });
  }, []);

  // 운영자가 신규 생성할 때는 워크스페이스가 안 박혀있으니 자기 워크스페이스로 채워주기 (저장 시 어차피 API 가 강제하지만 UI 표시 일관성)
  useEffect(() => {
    if (!isSysAdmin && isNew && workspaceId && !formData.workspace_id) {
      handleFieldChange("workspace_id", workspaceId);
    }
  }, [isSysAdmin, isNew, workspaceId, formData.workspace_id, handleFieldChange]);

  const canAccessSubTabs = !isNew && !!formData.email?.trim();
  const tabs = [
    { id: "basic", text: "사용자 정보", icon: "edit" },
    { id: "authors", text: "소속 권한", icon: "key", disabled: !canAccessSubTabs },
    { id: "sessions", text: "활성 세션", icon: "globe", disabled: !canAccessSubTabs },
  ];

  return (
    <div className="h-full">
      <TabPanel items={tabs} defaultTab="basic">
        <TabContent tabId="basic">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                <Button text="저장" onClick={() => handleSubmit(onSubmit)} />
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-auto">
              <TableGroup title="사용자 정보">
                <TableRow>
                  <TableCell label="이메일" required={isNew}>
                    <TextBox
                      fieldName="email"
                      value={formData.email}
                      readOnly={!isNew}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="이름">
                    <TextBox
                      fieldName="name"
                      value={formData.name}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="부서">
                    <TextBox
                      fieldName="dept"
                      value={formData.dept}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  {/* OEM: 워크스페이스 선택 불가 — 소속 확인용으로 readonly 노출 (생성은 서버가 단일 워크스페이스 강제, 수정은 기존값 보존). */}
                  <TableCell label="워크스페이스">
                    <SelectBox
                      fieldName="workspace_id"
                      value={formData.workspace_id}
                      items={workspaceOptions}
                      displayExpr="workspace_nm"
                      valueExpr="id"
                      showClearButton={isSysAdmin && !isOEM()}
                      readOnly={!isSysAdmin || isOEM()}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="승인여부" required>
                    <SelectBox
                      fieldName="appr_at"
                      value={formData.appr_at}
                      items={APPR_AT_OPTIONS}
                      displayExpr="text"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="사용여부" required>
                    <SelectBox
                      fieldName="use_at"
                      value={formData.use_at}
                      items={USE_AT_OPTIONS}
                      displayExpr="text"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="비밀번호" required={isNew} colSpan={3}>
                    <TextBox
                      fieldName="password"
                      value={formData.password}
                      showPasswordToggle
                      placeholder={isNew ? "" : "변경 시에만 입력하세요"}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="authors">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-auto">
              <TableGroup title="소속 권한">
                <TableRow>
                  <TableCell colSpan={4}>
                    <AdminUserAuthorGrid email={formData.email!} editable={true} height="500px" />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="sessions">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-auto">
              <TableGroup title="활성 세션">
                <TableRow>
                  <TableCell colSpan={4}>
                    <AdminUserSessionGrid email={formData.email!} editable={true} height="500px" />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
