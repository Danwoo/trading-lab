// hooks/shared/useTableExport.ts
"use client";

import { useCallback } from "react";
// 워크북 생성은 devextreme-exceljs-fork(MIT, exceljs 포크 — 순수 xlsx 라이터)를 쓴다.
// `devextreme/excel_exporter` 는 #341 로 사라졌다(그건 실제 그리드 인스턴스가 있어야 동작했다) —
// `useExcelExport` 도 이제 이 파일과 같은 순수 헬퍼(tableExport.ts)를 공유한다.
// `devextreme-exceljs-fork` 는 이름만 그럴 뿐 **DevExtreme 배포판이 아니다**(MIT exceljs 포크).
// #341 이 걷어낸 6종(devextreme·devextreme-react·@devexpress/utils·devexpress-diagram·
// devexpress-gantt·@devextreme/runtime)에 들어가지 않아 그대로 둔다.
import { Workbook } from "devextreme-exceljs-fork";
import { saveAs } from "file-saver";
import { showToast } from "@/components/shared/Feedback";
import type { GridColumn } from "@/types/grid";
import { buildExportFileName, numberFormatFor, toRowValues, toWorksheetColumnWidth } from "@/hooks/shared/tableExport";

interface Params<T> {
  columns: GridColumn<T>[];
  fetchAll: () => Promise<T[]>;
  fileName?: string;
}

/**
 * 그리드 커널용 엑셀 내보내기. `fetchAll` 이 돌려주는 전체 행을 받아 `columns` 정의
 * 순서·서식(dataType)대로 워크북을 만든다 — 화면에 보이는 페이지가 아니라 전체를 받는다.
 */
export function useTableExport<T>({ columns, fetchAll, fileName = "download" }: Params<T>): {
  handleExcelDownload: () => Promise<void>;
} {
  const handleExcelDownload = useCallback(async () => {
    try {
      const rows = await fetchAll();

      const workbook = new Workbook();
      const worksheet = workbook.addWorksheet("Data");

      worksheet.columns = columns.map((column) => ({
        header: column.caption,
        key: column.field,
        width: toWorksheetColumnWidth(column.width),
      }));

      worksheet.getRow(1).eachCell((cell) => {
        cell.font = { bold: true, name: "Arial", size: 11 };
        cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFE0E0E0" } };
        cell.alignment = { horizontal: "center", vertical: "middle" };
      });

      rows.forEach((row) => worksheet.addRow(toRowValues(row, columns)));

      columns.forEach((column, index) => {
        const numFmt = numberFormatFor(column.dataType, column.fractionDigits);
        if (!numFmt) return;
        worksheet.getColumn(index + 1).numFmt = numFmt;
      });

      const buffer = await workbook.xlsx.writeBuffer();
      const blob = new Blob([buffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      saveAs(blob, buildExportFileName(fileName));
    } catch (error) {
      showToast("Excel 다운로드 중 오류가 발생했습니다.", "error");
      throw error;
    }
  }, [columns, fetchAll, fileName]);

  return { handleExcelDownload };
}
