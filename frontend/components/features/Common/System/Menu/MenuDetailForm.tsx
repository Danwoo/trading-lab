// components/features/Common/System/Menu/MenuDetailForm.tsx
"use client";

import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, NumberBox, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { Menu } from "@/schemas/common/menu";
import { Icon, ICON_NAMES } from "@/components/shared/ui/primitives/icons";
import { isProtectedMenu } from "@/constants/protected";
import MenuAuthorGrid from "./MenuAuthorGrid";

type ParentOption = { value: string; label: string; use_at: string };

interface Props {
  isNew: boolean;
  initialData: Partial<Menu>;
  onSubmit: (data: Menu) => Promise<boolean>;
  onCancel?: () => void;
  parentOptions?: ParentOption[];
  isSysAdmin?: boolean;
}

const LEVEL_OPTIONS = [
  { value: 1, text: "1 - 폴더" },
  { value: 2, text: "2 - 프로그램" },
];

const USE_AT_OPTIONS = [
  { value: "Y", text: "사용" },
  { value: "N", text: "미사용" },
];

const parentItemRender = (item: ParentOption) => (
  <span style={item.use_at !== "Y" ? { color: "#c4c4c4" } : undefined}>{item.label}</span>
);

const ICON_ITEMS = ICON_NAMES.map((name) => ({ name }));

/**
 * 선택지 = 매핑에 있는 아이콘 + **지금 저장돼 있는 값**.
 *
 * #341 이 아이콘 매핑을 265→93 으로 줄여, 그 전에 저장된 메뉴는 목록에 없는 이름을 갖고 있을 수
 * 있다. 저장값을 목록에 얹지 않으면 트리거가 `fieldRender` 대신 원시 문자열로 떨어져 **아이콘
 * 없이 이름만** 그리고(다른 항목과 모양이 다르다), 드롭다운을 열었다 닫기만 해도 목록에 없는
 * 값이라 되돌릴 수 없다. 얹어 두면 fallback 아이콘 + 이름으로 다른 항목과 같은 모양이 되고
 * 원래 값이 목록에 남아 실수로 잃지 않는다.
 */
function iconItemsWith(currentIcon: string | null | undefined) {
  if (!currentIcon || ICON_NAMES.includes(currentIcon)) return ICON_ITEMS;
  return [...ICON_ITEMS, { name: currentIcon }];
}

const iconItemRender = (item: { name: string }) => (
  <div className="flex items-center gap-2">
    <Icon name={item.name} size={16} />
    <span>{item.name}</span>
  </div>
);

const iconFieldRender = (item: { name: string } | null) => (
  <div className="flex items-center gap-2">
    {item && <Icon name={item.name} size={16} className="flex-shrink-0" />}
    <span className="truncate">{item?.name ?? ""}</span>
  </div>
);

export default function MenuDetailForm({
  initialData,
  isNew,
  onSubmit,
  onCancel,
  parentOptions = [],
  isSysAdmin = false,
}: Props) {
  const isProtected = !isNew && !!(initialData as any).is_protected;
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Menu>(initialData);

  // 신규(메뉴ID 미확정) 일 때는 소속 권한 탭 비활성. 시스템 메뉴는 탭은 열리되 안내 문구만.
  const isSystemMenu = !isNew && isProtectedMenu(formData.menu_id ?? "");
  const tabs = [
    { id: "basic", text: "메뉴 정보", icon: "edit" },
    { id: "authors", text: "소속 권한", icon: "key", disabled: isNew },
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
              <TableGroup title="메뉴 정보">
                <TableRow>
                  <TableCell label="메뉴ID" required>
                    <TextBox
                      fieldName="menu_id"
                      value={formData.menu_id}
                      readOnly={!isNew}
                      onValueChanged={(_field, value) =>
                        handleFieldChange(
                          "menu_id",
                          String(value ?? "")
                            .replace(/\s/g, "")
                            .toLowerCase(),
                        )
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="메뉴명" required>
                    <TextBox
                      fieldName="menu_nm"
                      value={formData.menu_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="레벨" required>
                    <SelectBox
                      fieldName="menu_level"
                      value={formData.menu_level ?? undefined}
                      items={LEVEL_OPTIONS}
                      displayExpr="text"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      readOnly={!isNew}
                    />
                  </TableCell>
                  <TableCell label="정렬순서" required>
                    <NumberBox
                      fieldName="sort_ordr"
                      value={formData.sort_ordr}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      min={1}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="상위메뉴" required={formData.menu_level === 2}>
                    <SelectBox
                      fieldName="upper_menu_id"
                      value={formData.upper_menu_id ?? undefined}
                      items={parentOptions}
                      displayExpr="label"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      placeholder="선택하세요"
                      readOnly={formData.menu_level === 1 || isProtected}
                      itemRender={parentItemRender}
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
                      readOnly={isProtected}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="URL" colSpan={3}>
                    <TextBox
                      fieldName="url"
                      value={formData.url}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      readOnly={formData.menu_level === 1 || !isSysAdmin}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="아이콘" colSpan={3}>
                    <SelectBox
                      fieldName="icon"
                      items={iconItemsWith(formData.icon)}
                      value={formData.icon ?? undefined}
                      valueExpr="name"
                      displayExpr="name"
                      searchEnabled
                      showClearButton
                      placeholder="-- 선택 --"
                      itemRender={iconItemRender}
                      fieldRender={iconFieldRender}
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
                    {isSystemMenu ? (
                      <p className="text-sm text-gray-500 px-1 py-2">
                        시스템 메뉴는 권한별로 부여하지 않습니다. (권한 코드 매핑으로 자동 접근)
                      </p>
                    ) : (
                      <MenuAuthorGrid menuId={formData.menu_id!} editable height="500px" />
                    )}
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
