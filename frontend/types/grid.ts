// types/grid.ts
//
// DevExtreme 그리드를 대체하는 신규 그리드 커널의 타입 계약 (이슈 #242 O1).
// 서버로 나가는 필터·정렬 JSON 문법은 여기서 바꾸지 않는다 — 프론트 필터 파서(lib/ 아래
// 레거시 그리드 파서)와 백엔드 파서가 같은 문법을 그대로 소비한다.

import type { ReactNode } from "react";

export interface GridLookup {
  items: unknown[];
  valueField: string;
  displayField: string;
}

export interface GridColumn<T> {
  /** DB 컬럼명과 1:1 — 중첩 accessor 는 파이썬 파서가 400 으로 거절한다 */
  field: Extract<keyof T, string>;
  caption: string;
  width?: number;
  minWidth?: number;
  align?: "left" | "center" | "right";
  dataType?: "string" | "number" | "date" | "datetime";
  sortable?: boolean;
  filterable?: boolean;
  fixed?: "left" | "right";
  lookup?: GridLookup;
  /**
   * 소수부 최대 자릿수 (`dataType: "number"` 전용). 레거시 컬럼의 `format`(`#,##0.##`)에서 온다.
   *
   * **표시 서식이지 값이 아니다** — 그래서 `render` 로 문자열을 만들지 않고 자릿수만 싣는다.
   * 화면은 커널이 이 자릿수로 그리고, 엑셀은 셀에 숫자를 그대로 넣은 뒤 `numFmt` 로 같은
   * 자릿수를 건다. `render` 로 만들면 엑셀 셀이 `"71,250.5"` **문자열**이 돼 파일 안에서
   * 정렬·합계가 깨진다 (#341 이관 직후 9개 레거시 화면이 그 상태였다).
   */
  fractionDigits?: number;
  render?: (row: T) => ReactNode;
}

// ── 레거시 그리드(`components/shared/DataGrid/`)의 컬럼 선언 ────────────────────
//
// 관리자 CRUD 화면 28개가 이 모양으로 컬럼을 선언한다. 원래는 `DataGridTypes.Column`
// (devextreme-react/data-grid)을 직접 import 했는데, #341 로 devextreme 을 걷어내면서
// **화면을 건드리지 않으려고** 같은 키 이름으로 우리 타입을 세웠다. `DataGrid/legacyColumns.ts`
// 가 이것을 위의 `GridColumn` 으로 변환해 `DataTable` 커널에 넘긴다.
//
// **새 화면은 `GridColumn` 을 쓴다** — 이 타입은 이관 잔재이고, 두 모양을 하나로 합치는 것은
// 별도 작업이다(그러려면 화면 28개의 컬럼 배열을 전부 고쳐야 한다).

export interface LegacyGridLookup {
  dataSource: unknown[];
  displayExpr: string;
  valueExpr: string;
}

export interface LegacyGridColumn {
  /** DB 컬럼명. 비어 있으면 그 컬럼은 무시된다(이관 전 `MasterGrid` 의 filter 와 같은 동작). */
  dataField?: string;
  caption?: string;
  /** px. 문자열("120px")도 받아 숫자로 읽는다 — 이관 전 위젯이 둘 다 받았다. */
  width?: number | string;
  minWidth?: number;
  dataType?: "string" | "number" | "date" | "datetime" | "boolean" | "object";
  alignment?: "left" | "center" | "right";
  allowSorting?: boolean;
  allowFiltering?: boolean;
  /** false 면 화면에도 엑셀에도 나오지 않는다. */
  visible?: boolean;
  /** 가로 스크롤 시 고정. 위치는 `fixedPosition`(기본 left). */
  fixed?: boolean;
  fixedPosition?: "left" | "right";
  /**
   * 숫자·날짜 표시 형식(DevExtreme 패턴 문자열). 커널은 `dataType` 으로 서식을 정하므로
   * **소수부 자릿수만** 여기서 읽는다(`#,##0.##` → 최대 2자리). 그 밖의 패턴은 무시된다 —
   * 이관 전 전수 조사에서 쓰이던 형태가 이 하나뿐이었다.
   */
  format?: string;
  /** 코드값 → 표시명 매핑. 필터 행도 이 목록을 드롭다운으로 쓴다. */
  lookup?: LegacyGridLookup;
  /** 셀을 직접 그린다. 이관 전 시그니처(`cellData.data`/`.value`)를 유지한다. */
  cellRender?: (cellData: { data: any; value: any }) => React.ReactNode;
  /** 기본 서식 결과를 마지막에 한 번 더 다듬는다. */
  customizeText?: (cellInfo: { value: any; valueText: string }) => string;
}

export interface GridSort {
  selector: string;
  desc: boolean;
}

export interface GridQuery {
  skip: number;
  take?: number;
  filter?: unknown[];
  sort?: GridSort[];
}
