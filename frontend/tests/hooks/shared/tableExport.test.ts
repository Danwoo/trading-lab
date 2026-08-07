import { describe, expect, it } from "vitest";

import { buildExportFileName, numberFormatFor, toRowValues, toWorksheetColumnWidth } from "@/hooks/shared/tableExport";
import type { GridColumn } from "@/types/grid";

// buildExportFileName 은 화면 표시(사용자 타임존, #263)와 다르게 항상 KST 로 고정한다 —
// 기존 useExcelExport(hooks/shared/useExcelExport.ts) 와 같은 규칙을 유지해야 한다는 오더
// 제약을 이 테스트가 직접 검증한다.
describe("buildExportFileName — 파일명 타임스탬프는 KST 고정", () => {
  it("UTC 입력을 KST(+9h)로 변환해 {fileName}_{yyyy-MM-dd_HH-mm-ss}.xlsx 를 만든다", () => {
    // 2026-08-01 10:30:45 UTC == 2026-08-01 19:30:45 KST
    const utc = new Date("2026-08-01T10:30:45.000Z");
    expect(buildExportFileName("watchlist", utc)).toBe("watchlist_2026-08-01_19-30-45.xlsx");
  });

  it("KST 로 넘어가면서 날짜가 바뀌는 경계도 정확히 반영한다", () => {
    // 2026-08-01 20:15:00 UTC == 2026-08-02 05:15:00 KST — 날짜 자체가 넘어간다.
    const utc = new Date("2026-08-01T20:15:00.000Z");
    expect(buildExportFileName("orders", utc)).toBe("orders_2026-08-02_05-15-00.xlsx");
  });

  it("한 자리 월·일·시·분·초를 0으로 패딩한다", () => {
    // 2026-01-02 00:05:09 UTC == 2026-01-02 09:05:09 KST
    const utc = new Date("2026-01-02T00:05:09.000Z");
    expect(buildExportFileName("code", utc)).toBe("code_2026-01-02_09-05-09.xlsx");
  });
});

describe("toWorksheetColumnWidth — px → 엑셀 열 단위 (기존 useExcelExport 와 동일 비율 /8)", () => {
  it("지정한 width 를 8로 나눈다", () => {
    expect(toWorksheetColumnWidth(160)).toBe(20);
  });

  it("width 가 없으면 기본 120px 기준으로 계산한다", () => {
    expect(toWorksheetColumnWidth(undefined)).toBe(15);
  });
});

describe("numberFormatFor — dataType 별 엑셀 numFmt", () => {
  it("number 는 천단위 구분", () => {
    expect(numberFormatFor("number")).toBe("#,##0");
  });
  it("date/datetime 은 각각의 날짜 포맷", () => {
    expect(numberFormatFor("date")).toBe("yyyy-mm-dd");
    expect(numberFormatFor("datetime")).toBe("yyyy-mm-dd hh:mm:ss");
  });
  it("string 이거나 미지정이면 서식을 주지 않는다", () => {
    expect(numberFormatFor("string")).toBeUndefined();
    expect(numberFormatFor(undefined)).toBeUndefined();
  });
});

describe("toRowValues — 행 → 워크북 addRow 가 받는 key 매핑", () => {
  interface Row {
    ticker: string;
    price: number | null;
  }
  const columns: GridColumn<Row>[] = [
    { field: "ticker", caption: "종목코드" },
    { field: "price", caption: "가격" },
  ];

  it("컬럼 field 를 key 로 값을 뽑는다", () => {
    expect(toRowValues({ ticker: "005930", price: 70000 }, columns)).toEqual({ ticker: "005930", price: 70000 });
  });

  it("null/undefined 값은 빈 문자열로 치환한다 — exceljs 가 null 셀을 다르게 렌더하는 것을 피한다", () => {
    expect(toRowValues({ ticker: "005930", price: null }, columns)).toEqual({ ticker: "005930", price: "" });
  });
});

// 이슈 #242 O5 실측 회귀 — 화면 셀은 `render` 로 공통코드를 이름으로 보여주는데, 내보내기가
// 원본 필드(코드)를 그대로 썼다. 화면과 파일이 같은 해석기를 쓰는지 이 블록이 고정한다.
describe("toRowValues — render 가 있는 컬럼(공통코드 룩업 등)은 화면과 같은 값을 내보낸다", () => {
  interface Row {
    ticker: string;
    use_at: string;
  }

  it("render 결과가 문자열이면 원본 필드(코드) 대신 그 값을 쓴다", () => {
    const columns: GridColumn<Row>[] = [
      { field: "ticker", caption: "티커" },
      { field: "use_at", caption: "사용여부", render: (row) => (row.use_at === "Y" ? "사용" : "미사용") },
    ];

    expect(toRowValues({ ticker: "005930", use_at: "Y" }, columns)).toEqual({
      ticker: "005930",
      use_at: "사용",
    });
  });

  it("render 결과가 문자열/숫자가 아니면(엘리먼트 등) 원본 필드 값으로 되돌아간다", () => {
    const columns: GridColumn<Row>[] = [
      { field: "ticker", caption: "티커" },
      { field: "use_at", caption: "사용여부", render: () => null },
    ];

    expect(toRowValues({ ticker: "005930", use_at: "Y" }, columns)).toEqual({
      ticker: "005930",
      use_at: "Y",
    });
  });
});

// PR #417 독립 리뷰 「보통 5」 — 이관 직후 엑셀의 날짜·서식 숫자 컬럼이 텍스트 셀로 퇴화했다.
// `numFmt` 는 걸려 있었지만 셀 값이 API 가 준 ISO 문자열이라 엑셀이 서식을 무시했고, `format`
// 있는 숫자는 `toLocaleString` 결과("71,250.5")가 셀에 들어가 텍스트가 됐다 — 파일 안에서
// 정렬·합계가 깨진다. 이 블록은 셀 값이 **원시 타입**으로 나가는지를 고정한다.
describe("toRowValues — 날짜·숫자 셀은 원시 타입으로 나간다 (#417 엑셀 퇴화)", () => {
  interface Row {
    reg_dt: string | null;
    amount: string | number;
    note: string;
  }
  const columns: GridColumn<Row>[] = [
    { field: "reg_dt", caption: "등록일시", dataType: "datetime" },
    { field: "amount", caption: "금액", dataType: "number" },
    { field: "note", caption: "비고", dataType: "string" },
  ];

  it("ISO 문자열 날짜는 Date 객체가 된다 — 그래야 numFmt 가 먹고 엑셀에서 날짜로 정렬된다", () => {
    const values = toRowValues({ reg_dt: "2026-08-01T10:30:45.000Z", amount: 1, note: "x" }, columns);
    expect(values.reg_dt).toBeInstanceOf(Date);
  });

  // 엑셀은 날짜를 타임존 없는 일련번호로 저장하고 exceljs 는 그 값을 UTC 에폭에서 만든다 —
  // 인스턴트를 그대로 넣으면 파일에 **UTC 벽시계**가 찍혀 화면과 시간이 어긋난다(KST 면 −9h).
  // 셀에 들어가는 Date 는 "UTC 필드 = 지역 벽시계" 여야 한다.
  it("셀 Date 의 UTC 필드는 화면과 같은 지역 벽시계다", () => {
    const instant = new Date("2026-08-01T10:30:45.000Z");
    const values = toRowValues({ reg_dt: instant.toISOString(), amount: 1, note: "x" }, columns);
    const cell = values.reg_dt as Date;

    const pad = (n: number) => String(n).padStart(2, "0");
    const localWallClock = `${instant.getFullYear()}-${pad(instant.getMonth() + 1)}-${pad(instant.getDate())} ${pad(
      instant.getHours(),
    )}:${pad(instant.getMinutes())}:${pad(instant.getSeconds())}`;
    const cellWallClock = `${cell.getUTCFullYear()}-${pad(cell.getUTCMonth() + 1)}-${pad(cell.getUTCDate())} ${pad(
      cell.getUTCHours(),
    )}:${pad(cell.getUTCMinutes())}:${pad(cell.getUTCSeconds())}`;

    expect(cellWallClock).toBe(localWallClock);
  });

  it("숫자 컬럼의 문자열 값은 number 가 된다 — 엑셀에서 합계가 선다", () => {
    const values = toRowValues({ reg_dt: null, amount: "71250.5", note: "x" }, columns);
    expect(values.amount).toBe(71250.5);
  });

  it("파싱 못 하는 값은 원값 그대로 둔다 — 빈칸으로 두면 '값이 없다'와 구분이 안 된다", () => {
    const values = toRowValues({ reg_dt: "알 수 없음", amount: "N/A", note: "x" }, columns);
    expect(values.reg_dt).toBe("알 수 없음");
    expect(values.amount).toBe("N/A");
  });

  it("문자열 컬럼은 손대지 않는다", () => {
    const values = toRowValues({ reg_dt: null, amount: 1, note: "2026-08-01" }, columns);
    expect(values.note).toBe("2026-08-01");
  });
});

describe("numberFormatFor — 소수부 자릿수 (#417)", () => {
  it("자릿수가 있으면 그만큼 소수부를 갖는 서식을 만든다 — 화면과 파일이 같은 자릿수", () => {
    expect(numberFormatFor("number", 2)).toBe("#,##0.00");
    expect(numberFormatFor("number", 1)).toBe("#,##0.0");
  });

  it("자릿수가 없거나 0 이면 정수 서식 그대로다", () => {
    expect(numberFormatFor("number", 0)).toBe("#,##0");
    expect(numberFormatFor("number")).toBe("#,##0");
  });
});
