// components/features/Portfolio/PortfolioHoldingGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { TextBox, SelectBox, NumberBox, TextArea } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { selectHoldingList, createHolding, updateHolding, deleteHolding } from "@/services/portfolio/portfolioService";
import { Holding, HoldingOut } from "@/schemas/portfolio/portfolio";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";

interface Props {
  portfolioId: string;
  onSelectionChanged?: (holding: HoldingOut | null) => void;
  height?: string;
  editable?: boolean;
  codeList?: any;
}

const PortfolioHoldingGrid: React.FC<Props> = ({
  portfolioId,
  onSelectionChanged,
  height = "100%",
  editable = false,
  codeList,
}) => {
  // 보유종목 등록·수정·삭제는 `require_role` 이 걸린 쓰기다 (`/portfolio/{id}/holding`) — #341.
  const writeAccess = useWriteAccess();
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "ticker", caption: "종목코드", width: 100 },
    { dataField: "holding_nm", caption: "종목명", width: 180 },
    {
      // 관심종목 그리드와 같은 코드 그룹(5000)을 쓴다 — lookup 이라 필터 행도 표시명 드롭다운이
      // 된다(#321). 기존 행은 백필하지 않아 비어 있을 수 있다(#328).
      dataField: "market",
      caption: "시장",
      width: 100,
      lookup: {
        dataSource: codeList?.market,
        displayExpr: "code_nm",
        valueExpr: "code",
      },
    },
    { dataField: "quantity", caption: "수량", width: 100, dataType: "number" },
    { dataField: "avg_price", caption: "평균단가", width: 110, dataType: "number", format: "#,##0.##" },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 100,
      lookup: {
        dataSource: codeList?.useAt,
        displayExpr: "code_nm",
        valueExpr: "code",
      },
    },
    { dataField: "description", caption: "설명", minWidth: 150 },
  ];

  return (
    <DetailGridPanel
      fetchGrid={async (params: any) => await selectHoldingList({ ...params, portfolio_id: portfolioId })}
      columns={GRID_COLUMNS}
      height={height}
      apiService={{
        create: async (data: Holding) => {
          await createHolding({ ...data, portfolio_id: portfolioId });
        },
        update: async (data: Holding) => {
          await updateHolding({ ...data, portfolio_id: portfolioId });
        },
        delete: async (data: Holding) => {
          await deleteHolding({ ...data, portfolio_id: portfolioId });
        },
      }}
      FormComponent={FormComponent}
      formProps={{ codeList }}
      defaultFormData={{ quantity: 0, avg_price: 0, use_at: "Y" }}
      editable={editable}
      writeGated={writeAccess.isDenied ? { halted: ["보유종목 등록", "수정", "삭제"] } : undefined}
      onSelectionChanged={onSelectionChanged}
    />
  );
};

const FormComponent: React.FC<{
  formData: Partial<Holding>;
  modalMode: "create" | "edit";
  onFieldChange: (field: string, value: any) => void;
  getFieldProps: (field: string) => any;
  codeList?: any;
}> = ({ formData, modalMode, onFieldChange, getFieldProps, codeList }) => {
  return (
    <TableGroup title="보유종목 정보">
      <TableRow>
        <TableCell label="종목코드" required>
          <TextBox
            fieldName="ticker"
            value={formData.ticker}
            readOnly={modalMode === "edit"}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="종목명" required>
          <TextBox
            fieldName="holding_nm"
            value={formData.holding_nm}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>

      <TableRow>
        <TableCell label="수량" required>
          <NumberBox
            fieldName="quantity"
            value={formData.quantity}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="평균단가" required>
          <NumberBox
            fieldName="avg_price"
            value={formData.avg_price}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>

      <TableRow>
        {/* 시장은 선택 필드다(스키마 Optional·기존 행 미백필) — 값이 채워지면 터미널의 종목
            패널이 열린다. 값의 정본은 공통코드 5000 으로, 관심종목 화면과 같은 목록이다. */}
        <TableCell label="시장">
          <SelectBox
            fieldName="market"
            value={formData.market}
            items={codeList?.market}
            showClearButton
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
        <TableCell label="사용여부" required>
          <SelectBox
            fieldName="use_at"
            value={formData.use_at}
            items={codeList?.useAt}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
          />
        </TableCell>
      </TableRow>

      <TableRow>
        <TableCell label="설명" colSpan={3}>
          <TextArea
            fieldName="description"
            value={formData.description}
            onValueChanged={onFieldChange}
            getFieldProps={getFieldProps}
            maxLength={1000}
            height={80}
          />
        </TableCell>
      </TableRow>
    </TableGroup>
  );
};

export default React.memo(PortfolioHoldingGrid);
