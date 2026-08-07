// @vitest-environment jsdom
//
// 이슈 #321 — 필터 행이 `col.lookup` 이 있는 컬럼(공통코드)엔 자유텍스트 대신 드롭다운을 내고,
// 방출하는 필터 조건은 화면 표시값(code_nm)이 아니라 raw 코드(valueField)여야 한다. 관심종목
// 화면 실측(그룹 1000: Y=사용/N=미사용)을 그대로 고정값으로 쓴다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { DataTableFilterRow } from "@/components/shared/DataTable/DataTableFilterRow";
import type { GridColumn } from "@/types/grid";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

interface Row {
  ticker: string;
  use_at: string;
  issuer_nm: string;
}

const USE_AT_COLUMN: GridColumn<Row> = {
  field: "use_at",
  caption: "사용여부",
  lookup: {
    items: [
      { code: "Y", code_nm: "사용" },
      { code: "N", code_nm: "미사용" },
    ],
    valueField: "code",
    displayField: "code_nm",
  },
};

const TICKER_COLUMN: GridColumn<Row> = { field: "ticker", caption: "티커" };

function renderFilterRow(columns: GridColumn<Row>[], onFilterChange = vi.fn()) {
  render(
    <table>
      <tbody>
        <tr>
          <DataTableFilterRow columns={columns} filter={undefined} onFilterChange={onFilterChange} columnLayout={{}} />
        </tr>
      </tbody>
    </table>,
  );
  return onFilterChange;
}

describe("DataTableFilterRow — 룩업 컬럼 필터 (#321)", () => {
  it("룩업이 있는 컬럼은 자유텍스트 input 이 아니라 표시명 select 를 렌더한다", () => {
    renderFilterRow([USE_AT_COLUMN]);

    expect(screen.queryByRole("textbox", { name: "사용여부 필터" })).toBeNull();
    expect(screen.getByRole("combobox", { name: "사용여부 필터" })).toBeTruthy();

    // 화면에 보이는 것과 같은 표시명(code_nm)이 옵션 라벨이다 — 사용자가 코드를 몰라도 된다.
    expect(screen.getByRole("option", { name: "사용" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "미사용" })).toBeTruthy();
  });

  it("표시명 '사용'을 고르면 방출되는 필터는 raw 코드 'Y' 에 대한 정확일치다 — 이름으로 필터를 걸어도 0건이 되지 않는다", () => {
    const onFilterChange = renderFilterRow([USE_AT_COLUMN]);

    const select = screen.getByRole("combobox", { name: "사용여부 필터" });
    fireEvent.change(select, { target: { value: "Y" } });

    // 룩업 select 는 debounce 없이 즉시 방출한다(이산 선택이므로).
    expect(onFilterChange).toHaveBeenCalledWith(["use_at", "=", "Y"]);
  });

  it("'전체'를 고르면(빈 값) 그 컬럼 조건이 필터에서 빠진다", () => {
    const onFilterChange = renderFilterRow([USE_AT_COLUMN]);
    const select = screen.getByRole("combobox", { name: "사용여부 필터" }) as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "Y" } });
    fireEvent.change(select, { target: { value: "" } });

    expect(onFilterChange).toHaveBeenLastCalledWith(undefined);
  });

  it("룩업 없는 컬럼은 기존대로 자유텍스트 input(contains) 이다 — 회귀 없음", () => {
    vi.useFakeTimers();
    const onFilterChange = vi.fn();
    render(
      <table>
        <tbody>
          <tr>
            <DataTableFilterRow
              columns={[TICKER_COLUMN]}
              filter={undefined}
              onFilterChange={onFilterChange}
              columnLayout={{}}
            />
          </tr>
        </tbody>
      </table>,
    );

    const input = screen.getByRole("textbox", { name: "티커 필터" });
    fireEvent.change(input, { target: { value: "005" } });
    expect(onFilterChange).not.toHaveBeenCalled(); // 400ms debounce 전
    vi.advanceTimersByTime(400);
    expect(onFilterChange).toHaveBeenCalledWith(["ticker", "contains", "005"]);
  });

  it("룩업 컬럼과 텍스트 컬럼을 함께 걸면 and 로 묶인다", () => {
    vi.useFakeTimers();
    const onFilterChange = renderFilterRow([USE_AT_COLUMN, TICKER_COLUMN]);
    const select = screen.getByRole("combobox", { name: "사용여부 필터" });
    fireEvent.change(select, { target: { value: "Y" } });

    const input = screen.getByRole("textbox", { name: "티커 필터" });
    fireEvent.change(input, { target: { value: "005930" } });

    // 룩업 변경은 즉시 나가고(위 검증), 텍스트 변경은 debounce 뒤에 같은 buildFilter 를 다시
    // 호출한다 — 마지막 호출이 두 조건을 and 로 묶은 결과여야 한다.
    vi.advanceTimersByTime(400);
    expect(onFilterChange).toHaveBeenLastCalledWith([["use_at", "=", "Y"], "and", ["ticker", "contains", "005930"]]);
  });
});
