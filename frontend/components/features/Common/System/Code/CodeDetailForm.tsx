"use client";

import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, TextArea, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { CodeGroup } from "@/schemas/common/code";
import CodeDetailGrid from "./CodeDetailGrid";

interface Props {
  isNew: boolean;
  initialData: Partial<CodeGroup>;
  onSubmit: (data: CodeGroup) => Promise<boolean>;
  onCancel?: () => void;
}

export default function CodeGroupDetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<CodeGroup>(initialData);

  const canAccessSubTabs = !isNew && !!formData.group_code?.trim();
  const tabs = [
    { id: "basic", text: "그룹코드", icon: "edit" },
    { id: "codes", text: "코드", icon: "hierarchy", disabled: !canAccessSubTabs },
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

            <div className="flex-1 overflow-auto">
              <TableGroup title="그룹코드 정보">
                <TableRow>
                  <TableCell label="그룹코드" required>
                    <TextBox
                      fieldName="group_code"
                      value={formData.group_code}
                      readOnly={!isNew}
                      onValueChanged={(_field, value) =>
                        handleFieldChange(
                          "group_code",
                          String(value ?? "")
                            .replace(/\s/g, "")
                            .toLowerCase(),
                        )
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="그룹코드명" required>
                    <TextBox
                      fieldName="group_code_nm"
                      value={formData.group_code_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="그룹코드설명" colSpan={3}>
                    <TextArea
                      fieldName="group_code_dc"
                      value={formData.group_code_dc}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      maxLength={200}
                      height={100}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="사용여부" required>
                    <SelectBox
                      fieldName="use_at"
                      value={formData.use_at}
                      items={[
                        { value: "Y", text: "Y" },
                        { value: "N", text: "N" },
                      ]}
                      displayExpr="text"
                      valueExpr="value"
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="" />
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="codes">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <TableGroup title="코드 목록">
                <TableRow>
                  <TableCell colSpan={4}>
                    <CodeDetailGrid groupCode={formData.group_code!} editable={true} height="500px" />
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
