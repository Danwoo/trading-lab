// components/shared/DataGrid/legacyColumns.tsx
//
// 레거시 컬럼 선언(`LegacyGridColumn`, 화면 28개가 쓰는 DevExtreme 모양) → 그리드 커널이 받는
// `GridColumn` 변환 (#341).
//
// 이 파일이 있는 이유: devextreme 을 걷어내면서 **화면의 컬럼 배열을 그대로 두기 위해서**다.
// 키 이름(`dataField`/`cellRender`/`lookup.displayExpr` …)만 옮겨 주면 화면은 한 줄도 안 바뀐다.
// 반대로 `DataTable` 커널은 `GridColumn` 하나만 알면 되므로 두 세계가 여기서만 만난다.
//
// 순수 함수다(훅·부수효과 없음) — 화면·엑셀 내보내기가 같은 변환 결과를 쓴다.

import type { GridColumn, LegacyGridColumn } from "@/types/grid";
import { formatDate, formatNumber } from "@/utils/common/formatters";

/** "120px" 같은 문자열 폭도 숫자로 읽는다. 못 읽으면 커널 기본값에 맡긴다. */
function toWidthPx(width: number | string | undefined): number | undefined {
  if (typeof width === "number") return width;
  if (typeof width !== "string") return undefined;
  const parsed = Number.parseInt(width, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

/** 커널이 아는 dataType 만 넘긴다 — boolean/object 는 문자열로 그린다(이관 전과 같다). */
function toDataType(dataType: LegacyGridColumn["dataType"]): GridColumn<unknown>["dataType"] {
  return dataType === "number" || dataType === "date" || dataType === "datetime" ? dataType : "string";
}

/** `#,##0.##` → 2 (소수부 최대 자릿수). 소수부 패턴이 없으면 undefined. */
function fractionDigitsOf(format: string | undefined): number | undefined {
  if (!format) return undefined;
  const fraction = format.split(".")[1];
  return fraction ? fraction.replace(/[^#0]/g, "").length : undefined;
}

/** 기본 셀 문자열 — `customizeText` 에 넘길 `valueText` 를 만들 때도 쓴다. */
function defaultText(value: unknown, dataType: LegacyGridColumn["dataType"]): string {
  if (value === null || value === undefined || value === "") return "";
  if (dataType === "number") return formatNumber(value as number, "number");
  if (dataType === "date") return formatDate(value, "date") ?? String(value);
  if (dataType === "datetime") return formatDate(value, "datetime") ?? String(value);
  return String(value);
}

/**
 * 레거시 컬럼 배열을 커널 컬럼 배열로 옮긴다.
 *
 * - `dataField` 가 비었거나 `visible === false` 인 컬럼은 버린다(이관 전 동작 유지).
 * - `cellRender`·`customizeText`·`lookup` 은 커널의 단일 진입점 `render` 로 합친다. 우선순위는
 *   `cellRender` > `customizeText` > `lookup` — 이관 전 DevExtreme 도 셀 템플릿이 서식 텍스트를,
 *   서식 텍스트가 룩업 표시명을 대체했다.
 * - **룩업 표시명을 `render` 로 내는 것이 중요하다.** 커널은 `lookup` 을 필터 행 드롭다운에만
 *   쓰고 셀 표시에는 쓰지 않는다. 엑셀 내보내기(`tableExport.ts`)도 `render` 결과를 읽으므로,
 *   여기서 `render` 를 안 만들면 화면엔 이름이 뜨는데 파일엔 코드가 새는 회귀가 난다
 *   (그 파일 주석의 실측 사례 — 통화 "원화(KRW)"→"KRW", 사용여부 "사용"→"Y").
 * - `lookup` 자체는 그대로 넘긴다 — 필터 행 드롭다운이 그것을 쓴다.
 */
export function toGridColumns<T>(columns: LegacyGridColumn[]): GridColumn<T>[] {
  return columns
    .filter((column) => column.dataField?.trim() && column.visible !== false)
    .map((column) => {
      const field = column.dataField as string;
      const { cellRender, customizeText, dataType, lookup } = column;
      const fractionDigits = dataType === "number" ? fractionDigitsOf(column.format) : undefined;

      let render: GridColumn<T>["render"];
      if (cellRender) {
        render = (row) => cellRender({ data: row, value: (row as Record<string, unknown>)[field] });
      } else if (customizeText) {
        render = (row) => {
          const value = (row as Record<string, unknown>)[field];
          return customizeText({ value, valueText: defaultText(value, dataType) });
        };
      } else if (lookup) {
        render = (row) => {
          const value = (row as Record<string, unknown>)[field];
          const match = (lookup.dataSource as Array<Record<string, unknown>>).find(
            (item) => item !== null && typeof item === "object" && item[lookup.valueExpr] === value,
          );
          // 목록에 없는 값은 원값을 그대로 보여준다 — 빈칸으로 두면 "값이 없다"와 구분이 안 된다.
          return match ? String(match[lookup.displayExpr] ?? "") : defaultText(value, dataType);
        };
      }

      return {
        field: field as GridColumn<T>["field"],
        caption: column.caption ?? field,
        width: toWidthPx(column.width),
        minWidth: column.minWidth,
        align: column.alignment,
        dataType: toDataType(dataType),
        sortable: column.allowSorting,
        filterable: column.allowFiltering,
        fixed: column.fixed ? (column.fixedPosition ?? "left") : undefined,
        lookup: column.lookup
          ? {
              items: column.lookup.dataSource,
              valueField: column.lookup.valueExpr,
              displayField: column.lookup.displayExpr,
            }
          : undefined,
        // 소수부 자릿수는 **표시 서식**이라 `render` 문자열이 아니라 값으로 싣는다 — 화면은
        // 커널이, 엑셀은 `numFmt` 가 같은 자릿수를 건다(GridColumn.fractionDigits 주석).
        fractionDigits,
        render,
      } satisfies GridColumn<T>;
    });
}
