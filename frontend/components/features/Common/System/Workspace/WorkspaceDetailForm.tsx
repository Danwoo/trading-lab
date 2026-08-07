// components/features/Common/System/Workspace/WorkspaceDetailForm.tsx
"use client";

import { useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { DualSelectGrid } from "@/components/shared/DataGrid";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { Workspace } from "@/schemas/common/workspace";
import WorkspaceDomainGrid from "./WorkspaceDomainGrid";
import { selectWorkspaceMenus, addWorkspaceMenu, removeWorkspaceMenu } from "@/services/common/workspaceService";
import { isOEM } from "@/utils/common/edition";

interface Props {
  isNew: boolean;
  initialData: Partial<Workspace>;
  onSubmit: (data: Workspace) => Promise<boolean>;
  onCancel?: () => void;
}

interface MenuRow {
  menu_id: string;
  menu_nm: string;
  use_at?: string | null;
}

const menuColumns: LegacyGridColumn[] = [
  { dataField: "menu_id", caption: "메뉴ID" },
  { dataField: "menu_nm", caption: "메뉴명" },
];

export default function WorkspaceDetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Workspace>(initialData);

  const [workspaceMenus, setWorkspaceMenus] = useState<MenuRow[]>([]);
  const [allMenus, setAllMenus] = useState<MenuRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedMenuIds, setSelectedMenuIds] = useState<string[]>([]);
  const [selectedWorkspaceMenuIds, setSelectedWorkspaceMenuIds] = useState<string[]>([]);

  const canAccessSubTabs = !isNew && formData.id != null;
  // OEM: 도메인 매핑 미사용 — 탭 숨김
  const tabs = [
    { id: "basic", text: "워크스페이스 정보", icon: "edit" },
    ...(isOEM() ? [] : [{ id: "domains", text: "이메일 도메인", icon: "hierarchy", disabled: !canAccessSubTabs }]),
    { id: "menus", text: "메뉴", icon: "menu", disabled: !canAccessSubTabs },
  ];

  const fetchMenus = async () => {
    if (formData.id == null) return;
    const result = await selectWorkspaceMenus(formData.id);
    if (result) {
      setWorkspaceMenus(
        result.workspaceMenus.map((m) => ({
          menu_id: m.menu_id,
          menu_nm: m.menu?.menu_nm ?? m.menu_id,
          use_at: m.menu?.use_at ?? null,
        })),
      );
      setAllMenus(
        result.allMenus
          .filter((m) => m.menu_level === 2)
          .map((m) => ({ menu_id: m.menu_id, menu_nm: m.menu_nm, use_at: m.use_at })),
      );
    }
  };

  useEffect(() => {
    if (isNew || formData.id == null) return;
    const load = async () => {
      setLoading(true);
      await fetchMenus();
      setLoading(false);
    };
    load();
  }, [formData.id]);

  const handleAddMenu = async () => {
    if (selectedMenuIds.length === 0) {
      showToast("추가할 메뉴를 선택해주세요.", "warning");
      return;
    }
    const newIds = selectedMenuIds.filter((id) => !workspaceMenus.map((m) => m.menu_id).includes(id));
    if (newIds.length === 0) {
      showToast("이미 추가된 메뉴입니다.", "warning");
      return;
    }
    for (const menu_id of newIds) {
      try {
        await addWorkspaceMenu(formData.id!, menu_id);
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
      }
    }
    setSelectedMenuIds([]);
    await fetchMenus();
  };

  const handleRemoveMenu = async () => {
    if (selectedWorkspaceMenuIds.length === 0) {
      showToast("제거할 메뉴를 선택해주세요.", "warning");
      return;
    }
    for (const menu_id of selectedWorkspaceMenuIds) {
      try {
        await removeWorkspaceMenu(formData.id!, menu_id);
      } catch (error) {
        showMessage("오류", <div>{getApiErrorMessage(error)}</div>);
        break;
      }
    }
    setSelectedWorkspaceMenuIds([]);
    await fetchMenus();
  };

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

            <div className="flex-1 overflow-auto">
              <TableGroup title="워크스페이스 정보">
                <TableRow>
                  <TableCell label="워크스페이스ID">
                    <TextBox
                      fieldName="id"
                      value={formData.id != null ? String(formData.id) : ""}
                      readOnly
                      onValueChanged={() => {}}
                    />
                  </TableCell>
                  <TableCell label="워크스페이스코드" required>
                    <TextBox
                      fieldName="workspace_code"
                      value={formData.workspace_code}
                      readOnly={!isNew}
                      placeholder="예: acme"
                      onValueChanged={(_field, value) =>
                        handleFieldChange(
                          "workspace_code",
                          String(value ?? "")
                            .replace(/\s/g, "")
                            .toLowerCase(),
                        )
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="워크스페이스명" required>
                    <TextBox
                      fieldName="workspace_nm"
                      value={formData.workspace_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="사용여부" required>
                    <SelectBox
                      fieldName="use_at"
                      value={formData.use_at}
                      items={[
                        { value: "Y", text: "사용" },
                        { value: "N", text: "미사용" },
                      ]}
                      displayExpr="text"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        {!isOEM() && (
          <TabContent tabId="domains">
            <div className="h-full flex flex-col">
              <div className="flex-shrink-0 mb-2">
                <div className="flex gap-2 justify-end">
                  {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
                </div>
              </div>

              <div className="flex-1 overflow-auto">
                <TableGroup title="이메일 도메인 목록">
                  <TableRow>
                    <TableCell colSpan={4}>
                      <WorkspaceDomainGrid workspaceId={formData.id!} editable={true} height="500px" />
                    </TableCell>
                  </TableRow>
                </TableGroup>
              </div>
            </div>
          </TabContent>
        )}

        <TabContent tabId="menus">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <DualSelectGrid
                title="워크스페이스 메뉴 관리"
                leftTitle="전체 메뉴"
                rightTitle="부여된 메뉴"
                leftData={allMenus.filter((m) => !workspaceMenus.some((cm) => cm.menu_id === m.menu_id))}
                rightData={workspaceMenus}
                leftColumns={menuColumns}
                rightColumns={menuColumns}
                leftKeyExpr="menu_id"
                rightKeyExpr="menu_id"
                loading={loading}
                fillHeight
                inactiveExpr="use_at"
                onAdd={handleAddMenu}
                onRemove={handleRemoveMenu}
                onLeftSelectionChanged={setSelectedMenuIds}
                onRightSelectionChanged={setSelectedWorkspaceMenuIds}
              />
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
