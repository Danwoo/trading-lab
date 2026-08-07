// hooks/shared/tableExport.ts
//
// useTableExport 가 쓰는 순수 로직 — devextreme-exceljs-fork·file-saver 등 브라우저 전용
// 부수효과 모듈을 import 하지 않는다. gridQuery.ts 와 같은 이유로 분리한다: vitest 는 "node"
// 환경만 쓰므로(O0, #262), 워크북·파일 저장 코드까지 물고 오면 이 계산만 검증하려는 테스트가
// 함께 깨진다.

import { getKSTTime } from "@/utils/common/timeUtils";
import type { GridColumn } from "@/types/grid";

// 파일명 타임스탬프는 **KST 고정**이다 — #263 로 화면에 보이는 시각은 사용자 타임존으로
// 바뀌었지만, 다운로드 파일명 규칙은 기존 `useExcelExport`(hooks/shared/useExcelExport.ts)와
// 어긋나면 안 된다(#242 O1 2단계 오더 명시). 화면 표시와 파일명이 다른 타임존 기준을 쓰는
// 이 비대칭은 의도된 것이다: 파일명은 "언제 받았는지"를 가리키는 안정적인 정렬 키 역할도
// 겸하고 있어(같은 이름 패턴으로 다운로드 폴더에서 시간순 정렬), 이미 여러 화면에 뿌려진
// 기존 규칙을 이 신규 커널만 다른 타임존으로 바꾸면 같은 앱 안에서 파일명 규칙이 갈린다.
export function buildExportFileName(fileName: string, now: Date = new Date()): string {
  const kst = getKSTTime(now);
  const year = kst.getUTCFullYear();
  const month = String(kst.getUTCMonth() + 1).padStart(2, "0");
  const day = String(kst.getUTCDate()).padStart(2, "0");
  const hours = String(kst.getUTCHours()).padStart(2, "0");
  const minutes = String(kst.getUTCMinutes()).padStart(2, "0");
  const seconds = String(kst.getUTCSeconds()).padStart(2, "0");
  return `${fileName}_${year}-${month}-${day}_${hours}-${minutes}-${seconds}.xlsx`;
}

const DEFAULT_COLUMN_WIDTH_PX = 120;
// 기존 useExcelExport 와 동일한 px → 엑셀 열 단위 환산 비율.
const EXCEL_WIDTH_DIVISOR = 8;

export function toWorksheetColumnWidth(widthPx: number | undefined): number {
  return (widthPx ?? DEFAULT_COLUMN_WIDTH_PX) / EXCEL_WIDTH_DIVISOR;
}

/**
 * 컬럼에 걸 엑셀 서식(`numFmt`).
 *
 * 서식은 **셀 값이 원시 타입일 때만** 의미가 있다 — 날짜 셀에 ISO 문자열, 숫자 셀에
 * `"71,250.5"` 같은 문자열이 들어가면 엑셀은 그것을 텍스트로 보고 서식을 무시한다.
 * 그래서 아래 `toTypedCellValue` 가 이 세 dataType 의 셀 값을 Date·number 로 만들어 넣는다.
 */
export function numberFormatFor(
  dataType: GridColumn<unknown>["dataType"],
  fractionDigits?: number,
): string | undefined {
  switch (dataType) {
    case "number":
      // 레거시 컬럼의 `format`(`#,##0.##`) 자릿수를 그대로 옮긴다 — 화면과 파일이 같은 소수부.
      return fractionDigits ? `#,##0.${"0".repeat(fractionDigits)}` : "#,##0";
    case "date":
      return "yyyy-mm-dd";
    case "datetime":
      return "yyyy-mm-dd hh:mm:ss";
    default:
      return undefined;
  }
}

// 컬럼에 `render` 가 있으면(공통코드 룩업 등, 화면 셀이 이미 이름으로 그리는 값) 내보내기도
// 같은 값을 쓴다 — 화면과 파일이 서로 다른 해석기를 쓰면 조용히 갈라진다(이슈 #242 O5, 관심
// 종목 화면 실측: 엑셀에만 코드가 그대로 새는 회귀가 실제로 났다 — 통화 "원화(KRW)"→"KRW",
// 우선순위 "높음"→"1", 사용여부 "사용"→"Y"). `render` 가 리터럴 문자열/숫자가 아니라 엘리먼트
// (아이콘·배지 등)를 돌려주면 셀에 그대로 넣을 수 없으므로 원본 필드 값으로 되돌아간다 —
// render 가 없는 일반 컬럼에도 항상 안전하게 동작해야 하기 때문이다.
function resolveExportValue<T>(row: T, column: GridColumn<T>, rawValue: unknown): unknown {
  if (column.render) {
    const rendered = column.render(row);
    if (typeof rendered === "string" || typeof rendered === "number") return rendered;
  }
  return toTypedCellValue(rawValue, column.dataType);
}

const MINUTE_MS = 60 * 1000;

/**
 * 엑셀 날짜 셀에 넣을 `Date` — **화면에 보이는 벽시계를 UTC 필드에 담은** 값.
 *
 * 엑셀은 날짜를 타임존 없는 일련번호로 저장하고, exceljs 는 그 일련번호를 `d.getTime()`(UTC
 * 에폭)에서 바로 만든다(`utils.dateToExcel`). 그래서 인스턴트를 그대로 넣으면 엑셀이 **UTC
 * 벽시계**를 보여준다 — KST 사용자에겐 화면보다 9시간 이른 시각이 파일에 찍힌다.
 *
 * 오프셋을 미리 더해 "UTC 필드 = 지역 벽시계"로 만들면 엑셀이 화면과 같은 시각을 그리면서
 * 날짜 정렬·필터도 정상 동작한다. 오프셋은 그 인스턴트 기준으로 읽으므로 서머타임도 따라간다.
 */
function toExcelWallClockDate(instant: Date): Date {
  return new Date(instant.getTime() - instant.getTimezoneOffset() * MINUTE_MS);
}

/**
 * 엑셀 셀에 넣을 **원시 타입** 값 — 날짜는 `Date`, 숫자는 `number`.
 *
 * 이관 전 `exportDataGrid` 는 파싱된 Date·원본 숫자로 셀을 만들었다. 이관 직후에는 API 가 준
 * ISO 문자열이 그대로 셀에 들어가 위 `numFmt` 가 무력해졌고, 엑셀 안에서 날짜 정렬·숫자 합계가
 * 깨졌다(레거시 화면 9곳). 파싱에 실패하면 원값을 그대로 둔다 — 빈칸으로 두면 "값이 없다"와
 * 구분이 안 된다.
 */
function toTypedCellValue(rawValue: unknown, dataType: GridColumn<unknown>["dataType"]): unknown {
  if (rawValue === null || rawValue === undefined || rawValue === "") return "";
  if (dataType === "date" || dataType === "datetime") {
    if (rawValue instanceof Date) return toExcelWallClockDate(rawValue);
    if (typeof rawValue !== "string" && typeof rawValue !== "number") return rawValue;
    const parsed = new Date(rawValue);
    return Number.isNaN(parsed.getTime()) ? rawValue : toExcelWallClockDate(parsed);
  }
  if (dataType === "number") {
    if (typeof rawValue === "number") return rawValue;
    if (typeof rawValue !== "string") return rawValue;
    const parsed = Number(rawValue);
    return Number.isNaN(parsed) ? rawValue : parsed;
  }
  return rawValue;
}

/** 행 객체를 exceljs 의 key 기반 addRow 가 받는 { [field]: value } 형태로 변환한다. */
export function toRowValues<T>(row: T, columns: GridColumn<T>[]): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  columns.forEach((column) => {
    const rawValue = (row as Record<string, unknown>)[column.field] ?? "";
    values[column.field] = resolveExportValue(row, column, rawValue);
  });
  return values;
}
