// @vitest-environment jsdom
//
// #443 회귀 그물 — 정렬 헤더가 **정렬 상태를 읽어 주는 쪽에도 알린다**(`aria-sort`).
//
// Cycle 7 발굴 B-36: 컬럼 헤더는 `<button>` 이라 키보드로 누를 수 있는데 `th` 에 `aria-sort` 가
// 없었다. 눈으로 보는 사람은 ▲▼ 로 알지만 스크린리더 사용자는 **지금 무엇으로 정렬돼 있는지
// 알 수 없다.**
//
// 증명하는 것: 정렬 가능한 열은 상태에 따라 ascending/descending/none 을 내고, **정렬 불가 열에는
// 속성이 아예 없다**(있으면 「정렬할 수 있다」는 잘못된 신호가 된다).
// 증명하지 못하는 것: 실제 스크린리더가 그것을 읽는지 — jsdom 은 접근성 트리를 만들지 않는다.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { createColumnHelper, getCoreRowModel, useReactTable } from "@tanstack/react-table";

import { DataTableHeader } from "@/components/shared/DataTable/DataTableHeader";

afterEach(cleanup);

interface Row {
  name: string;
  memo: string;
}

const helper = createColumnHelper<Row>();

function Harness({ sorting }: { sorting: { id: string; desc: boolean }[] }) {
  const table = useReactTable({
    data: [{ name: "가", memo: "나" }],
    columns: [
      helper.accessor("name", { header: "이름", enableSorting: true }),
      helper.accessor("memo", { header: "메모", enableSorting: false }),
    ],
    state: { sorting },
    onSortingChange: () => {},
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <table>
      <DataTableHeader
        headerGroups={table.getHeaderGroups()}
        columns={[
          { field: "name", caption: "이름" },
          { field: "memo", caption: "메모" },
        ]}
        showSelectionColumn={false}
        selectionMode="none"
        allSelected={false}
        onToggleAll={() => {}}
        hasFilterableColumn={false}
        filter={undefined}
        onFilterChange={() => {}}
        columnLayout={{}}
        onColumnResize={() => {}}
      />
    </table>
  );
}

function headerCells() {
  return Array.from(document.querySelectorAll("th"));
}

describe("정렬 헤더가 정렬 상태를 알린다 (#443)", () => {
  it("정렬이 없으면 정렬 가능한 열은 none 이다", () => {
    render(<Harness sorting={[]} />);
    const [name] = headerCells();
    expect(name.getAttribute("aria-sort")).toBe("none");
  });

  it("오름차순이면 ascending, 내림차순이면 descending 이다", () => {
    const { unmount } = render(<Harness sorting={[{ id: "name", desc: false }]} />);
    expect(headerCells()[0].getAttribute("aria-sort")).toBe("ascending");
    unmount();

    render(<Harness sorting={[{ id: "name", desc: true }]} />);
    expect(headerCells()[0].getAttribute("aria-sort")).toBe("descending");
  });

  it("정렬 불가 열에는 aria-sort 가 아예 없다", () => {
    render(<Harness sorting={[]} />);
    const memo = headerCells()[1];
    expect(memo.hasAttribute("aria-sort")).toBe(false);
  });
});
