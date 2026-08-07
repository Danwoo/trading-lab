// hooks/shared/useExcelExport.ts
"use client";

import { useCallback, useMemo } from "react";
// 워크북 생성은 devextreme-exceljs-fork(MIT — exceljs 포크, DevExtreme 배포판이 아니다)를 쓴다.
// `devextreme/excel_exporter` 는 #341 로 걷어냈다: 그건 실제 DevExtreme 그리드 인스턴스가
// 있어야 동작하는데 이제 그리드가 없다. 대신 `useTableExport` 와 같은 순수 헬퍼
// (`tableExport.ts`)를 공유한다 — 두 내보내기 경로가 서식·파일명 규칙에서 갈리지 않게.
import { Workbook } from "devextreme-exceljs-fork";
import { saveAs } from "file-saver";
import { showToast } from "@/components/shared/Feedback";
import type { LegacyGridColumn } from "@/types/grid";
import { toGridColumns } from "@/components/shared/DataGrid/legacyColumns";
import { buildExportFileName, numberFormatFor, toRowValues, toWorksheetColumnWidth } from "@/hooks/shared/tableExport";

interface Params<T> {
  /** `useMasterGridData()` 등이 돌려주는 `dataSource`. 전체 행은 그 `fetchAll()` 로 받는다. */
  dataSource: { fetchAll: () => Promise<T[]> };
  fileName?: string;
  columns: LegacyGridColumn[];
  onLoadingChange?: (loading: boolean) => void;
}

/**
 * 레거시 그리드 화면의 Excel 다운로드.
 *
 * 이관 전에는 그리드 인스턴스(`gridRef`)를 넘겨 DevExtreme 이 화면 상태 그대로 내보냈다.
 * 지금은 **현재 필터·정렬을 유지한 채 전체 행을 다시 받아**(`fetchAll`) 컬럼 정의대로 쓴다 —
 * 페이지에 보이는 만큼만 나가지 않는다는 점도 이관 전과 같다.
 *
 * 룩업 컬럼의 표시명은 `toGridColumns` 가 만든 `render` 를 통해 그대로 반영된다 — 화면엔
 * 이름이 뜨는데 파일엔 코드가 새는 회귀를 막는 자리다(`tableExport.ts` 주석의 실측 사례).
 */
export const useExcelExport = <T>({ dataSource, fileName = "download", columns, onLoadingChange }: Params<T>) => {
  const exportColumns = useMemo(() => toGridColumns<T>(columns), [columns]);

  const handleExcelDownload = useCallback(async () => {
    try {
      onLoadingChange?.(true);
      const rows = await dataSource.fetchAll();

      const workbook = new Workbook();
      const worksheet = workbook.addWorksheet("Data");

      worksheet.columns = exportColumns.map((column) => ({
        header: column.caption,
        key: column.field,
        width: toWorksheetColumnWidth(column.width),
      }));

      worksheet.getRow(1).eachCell((cell) => {
        cell.font = { bold: true, name: "Arial", size: 11 };
        cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFE0E0E0" } };
        cell.alignment = { horizontal: "center", vertical: "middle" };
      });

      rows.forEach((row) => worksheet.addRow(toRowValues(row, exportColumns)));

      exportColumns.forEach((column, index) => {
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
    } finally {
      onLoadingChange?.(false);
    }
  }, [dataSource, fileName, exportColumns, onLoadingChange]);

  return { handleExcelDownload };
};
