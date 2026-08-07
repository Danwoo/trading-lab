// components/features/Common/System/Author/AuthorDetailForm.tsx
"use client";

import { useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { DualSelectGrid } from "@/components/shared/DataGrid";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { Author } from "@/schemas/common/author";
import {
  selectAuthorUsers,
  selectAuthorMenus,
  addAuthorUser,
  removeAuthorUser,
  addAuthorMenu,
  removeAuthorMenu,
} from "@/services/common/authorService";
import { isProtectedMenu } from "@/constants/protected";

interface Props {
  isNew: boolean;
  initialData: Partial<Author>;
  onSubmit: (data: Author) => Promise<boolean>;
  onCancel?: () => void;
}

interface AuthorUser {
  author_id: string;
  user_id: string;
  user_nm: string;
  workspace_nm?: string;
}

interface UserOption {
  user_id: string;
  user_nm: string;
  use_at: string;
  appr_at: string;
  workspace_nm?: string;
}

interface AuthorMenu {
  menu_id: string;
  menu_nm: string;
  use_at?: string | null;
}

interface MenuOption {
  menu_id: string;
  menu_nm: string;
  use_at: string | null;
}

const menuColumns: LegacyGridColumn[] = [
  { dataField: "menu_id", caption: "메뉴ID" },
  { dataField: "menu_nm", caption: "메뉴명" },
];

export default function AuthorDetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Author>(initialData);

  const userColumns: LegacyGridColumn[] = [
    { dataField: "user_id", caption: "이메일" },
    { dataField: "user_nm", caption: "이름" },
    { dataField: "workspace_nm", caption: "워크스페이스" },
  ];

  const [authorUsers, setAuthorUsers] = useState<AuthorUser[]>([]);
  const [allUsers, setAllUsers] = useState<UserOption[]>([]);
  const [authorMenus, setAuthorMenus] = useState<AuthorMenu[]>([]);
  const [allMenus, setAllMenus] = useState<MenuOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [selectedAuthorUserIds, setSelectedAuthorUserIds] = useState<string[]>([]);
  const [selectedMenuIds, setSelectedMenuIds] = useState<string[]>([]);
  const [selectedAuthorMenuIds, setSelectedAuthorMenuIds] = useState<string[]>([]);
  const canAccessSubTabs = !isNew && !!formData.author_id?.trim();

  const tabs = [
    { id: "basic", text: "권한 정보", icon: "edit" },
    { id: "menus", text: "메뉴 권한", icon: "hierarchy", disabled: !canAccessSubTabs },
    { id: "users", text: "사용자 권한", icon: "group", disabled: !canAccessSubTabs },
  ];

  const fetchUsers = async () => {
    if (!formData.author_id) return;
    const result = await selectAuthorUsers(formData.author_id);
    if (result) {
      setAuthorUsers(
        result.authorUsers.map((u) => ({ ...u, use_at: u.use_at === "Y" && u.appr_at === "Y" ? "Y" : "N" })),
      );
      setAllUsers(result.allUsers.map((u) => ({ ...u, use_at: u.use_at === "Y" && u.appr_at === "Y" ? "Y" : "N" })));
    }
  };

  const fetchMenus = async () => {
    if (!formData.author_id) return;
    const result = await selectAuthorMenus(formData.author_id);
    if (result) {
      setAuthorMenus(
        result.authorMenus.map((m) => ({
          menu_id: m.menu_id,
          menu_nm: m.menu?.menu_nm ?? m.menu_id,
          use_at: m.menu?.use_at ?? null,
        })),
      );
      setAllMenus(
        result.allMenus
          .filter((m) => m.menu_level === 2 && !isProtectedMenu(m.menu_id))
          .map((m) => ({ menu_id: m.menu_id, menu_nm: m.menu_nm, use_at: m.use_at })),
      );
    }
  };

  useEffect(() => {
    if (isNew || !formData.author_id) return;
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchUsers(), fetchMenus()]);
      setLoading(false);
    };
    load();
  }, [formData.author_id]);

  const handleAddUser = async () => {
    if (selectedUserIds.length === 0) {
      showToast("추가할 사용자를 선택해주세요.", "warning");
      return;
    }
    const newIds = selectedUserIds.filter((id) => !authorUsers.map((u) => u.user_id).includes(id));
    if (newIds.length === 0) {
      showToast("이미 추가된 사용자입니다.", "warning");
      return;
    }
    for (const user_id of newIds) {
      try {
        await addAuthorUser(formData.author_id!, user_id);
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
      }
    }
    setSelectedUserIds([]);
    await fetchUsers();
  };

  const handleRemoveUser = async () => {
    if (selectedAuthorUserIds.length === 0) {
      showToast("제거할 사용자를 선택해주세요.", "warning");
      return;
    }
    for (const user_id of selectedAuthorUserIds) {
      try {
        await removeAuthorUser(formData.author_id!, user_id);
      } catch (error) {
        showMessage("오류", <div>{getApiErrorMessage(error)}</div>);
        break;
      }
    }
    setSelectedAuthorUserIds([]);
    await fetchUsers();
  };

  const handleAddMenu = async () => {
    if (selectedMenuIds.length === 0) {
      showToast("추가할 메뉴를 선택해주세요.", "warning");
      return;
    }
    const newIds = selectedMenuIds.filter((id) => !authorMenus.map((m) => m.menu_id).includes(id));
    if (newIds.length === 0) {
      showToast("이미 추가된 메뉴입니다.", "warning");
      return;
    }
    for (const menu_id of newIds) {
      try {
        await addAuthorMenu(formData.author_id!, menu_id);
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
      }
    }
    setSelectedMenuIds([]);
    await fetchMenus();
  };

  const handleRemoveMenu = async () => {
    if (selectedAuthorMenuIds.length === 0) {
      showToast("제거할 메뉴를 선택해주세요.", "warning");
      return;
    }
    for (const menu_id of selectedAuthorMenuIds) {
      try {
        await removeAuthorMenu(formData.author_id!, menu_id);
      } catch (error) {
        showMessage("오류", <div>{getApiErrorMessage(error)}</div>);
        break;
      }
    }
    setSelectedAuthorMenuIds([]);
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
            <div className="flex-1 min-h-0 overflow-auto">
              <TableGroup title="권한 정보">
                <TableRow>
                  <TableCell label="권한ID" required>
                    <TextBox
                      fieldName="author_id"
                      value={formData.author_id}
                      readOnly={!isNew}
                      onValueChanged={(_field, value) =>
                        handleFieldChange(
                          "author_id",
                          String(value ?? "")
                            .replace(/\s/g, "")
                            .toLowerCase(),
                        )
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="권한명" required>
                    <TextBox
                      fieldName="author_nm"
                      value={formData.author_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="menus">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>
            <div className="flex-1 min-h-0">
              {formData.is_sys_admin ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  시스템관리자 권한은 모든 메뉴에 접근할 수 있습니다.
                </div>
              ) : (
                <DualSelectGrid
                  title="메뉴 권한 관리"
                  leftTitle="전체 메뉴"
                  rightTitle="권한 부여된 메뉴"
                  leftData={allMenus.filter((m) => !authorMenus.some((am) => am.menu_id === m.menu_id))}
                  rightData={authorMenus}
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
                  onRightSelectionChanged={setSelectedAuthorMenuIds}
                />
              )}
            </div>
          </div>
        </TabContent>

        <TabContent tabId="users">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <DualSelectGrid
                title="사용자 권한 관리"
                leftTitle="전체 사용자"
                rightTitle="권한 부여된 사용자"
                leftData={allUsers.filter((u) => !authorUsers.some((au) => au.user_id === u.user_id))}
                rightData={authorUsers}
                leftColumns={userColumns}
                rightColumns={userColumns}
                leftKeyExpr="user_id"
                rightKeyExpr="user_id"
                loading={loading}
                fillHeight
                inactiveExpr="use_at"
                onAdd={handleAddUser}
                onRemove={handleRemoveUser}
                onLeftSelectionChanged={setSelectedUserIds}
                onRightSelectionChanged={setSelectedAuthorUserIds}
              />
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
