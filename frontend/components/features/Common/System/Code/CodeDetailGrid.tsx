// components/features/Common/System/Code/CodeDetailGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { TextBox, SelectBox, TextArea, NumberBox } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { selectCodeList, createCode, updateCode, deleteCode } from "@/services/common/codeService";
import { Code, CodeOut } from "@/schemas/common/code";

interface Props {
  groupCode: string;
  onSelectionChanged?: (code: CodeOut | null) => void;
  height?: string;
  editable?: boolean;
}

const CodeDetailGrid: React.FC<Props> = ({ groupCode, onSelectionChanged, height = "100%", editable = false }) => {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "code", caption: "코드", width: 100 },
    { dataField: "code_nm", caption: "코드명", width: 150 },
    { dataField: "code_nm_eng", caption: "영문명", width: 150 },
    { dataField: "sort_ordr", caption: "정렬순서", width: 100, dataType: "number" },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 100,
      lookup: {
        dataSource: [
          { value: "Y", text: "사용" },
          { value: "N", text: "미사용" },
        ],
        displayExpr: "text",
        valueExpr: "value",
      },
    },
    { dataField: "code_dc", caption: "코드설명", minWidth: 150 },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
  ];

  return (
    <DetailGridPanel
      fetchGrid={async (params: any) => {
        return await selectCodeList({
          ...params,
          group_code: groupCode,
        });
      }}
      columns={GRID_COLUMNS}
      height={height}
      apiService={{
        create: async (data: Code) => {
          await createCode({ ...data, group_code: groupCode });
        },
        update: async (data: Code) => {
          await updateCode(data);
        },
        delete: async (data: Code) => {
          await deleteCode(data);
        },
      }}
      FormComponent={FormComponent}
      defaultFormData={{
        sort_ordr: 1,
        use_at: "Y",
      }}
      editable={editable}
      onSelectionChanged={onSelectionChanged}
    />
  );
};

const FormComponent: React.FC<{
  formData: Partial<Code>;
  modalMode: "create" | "edit";
  onFieldChange: (field: string, value: any) => void;
  getFieldProps: (field: string) => any;
}> = ({ formData, modalMode, onFieldChange, getFieldProps }) => {
  return (
    <TableGroup title="코드 정보">
      <TableRow>
        <TableCell label="코드" required>
          <TextBox
            fieldName="code"
            value={formData.code}
            readOnly={modalMode === "edit"}
            onValueChanged={(_field, value) =>
              onFieldChange(
                "code",
                String(value ?? "")
                  .replace(/\s/g, "")
                  .toLowerCase(),
              )
            }
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="코드명" required>
          <TextBox
            fieldName="code_nm"
            value={formData.code_nm}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>

      <TableRow>
        <TableCell label="영문명">
          <TextBox
            fieldName="code_nm_eng"
            value={formData.code_nm_eng}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="정렬순서" required>
          <NumberBox
            fieldName="sort_ordr"
            value={formData.sort_ordr}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>

      <TableRow>
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
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="" />
      </TableRow>

      <TableRow>
        <TableCell label="코드설명" colSpan={3}>
          <TextArea
            fieldName="code_dc"
            value={formData.code_dc}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
            maxLength={200}
            height={80}
          />
        </TableCell>
      </TableRow>
    </TableGroup>
  );
};
export default React.memo(CodeDetailGrid);
