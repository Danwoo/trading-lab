// @vitest-environment jsdom
//
// #439 F26 — 상세 화면에서 「주기」가 숫자 `1` 로 떴다. 같은 화면의 「요일」은 「월」로 옮겨진다.
//
//   요일    월     ← 코드(mon)를 표시명으로 옮겼다
//   주기    1      ← 1(주간)·2(격주)·4(월간) 인데 숫자 그대로
//
// 폼에서는 「주간 ▾」으로 고르는 값인데 저장 후 상세에서 `1` 로 돌아온다.
//
// 뿌리는 `TableCell` 의 첫 줄이다: `typeof children !== "string"` 이면 매핑을 포기한다.
// `day_of_week` 는 문자열이라 되고 `period_weeks` 는 **숫자**라 안 됐다. 값의 타입이 화면의
// 말투를 가르는 것은 사용자가 알 수 없는 규칙이다.
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { TableCell } from "@/components/shared/Layout/TableCell";

const PERIOD = [
  { code: 1, code_nm: "주간" },
  { code: 2, code_nm: "격주" },
  { code: 4, code_nm: "월간" },
];
const DAYS = [
  { code: "mon", code_nm: "월" },
  { code: "tue", code_nm: "화" },
];

describe("코드 칸이 숫자 코드도 사람 말로 옮긴다", () => {
  it("숫자 코드를 표시명으로 옮긴다", () => {
    render(
      <TableCell label="주기" items={PERIOD}>
        {1}
      </TableCell>,
    );

    expect(screen.getByText("주간")).toBeTruthy();
    expect(screen.queryByText("1")).toBeNull();
  });

  it("문자열 코드는 종전대로 옮긴다 — 막는 범위가 넓어지지 않았다", () => {
    render(
      <TableCell label="요일" items={DAYS}>
        {"mon"}
      </TableCell>,
    );

    expect(screen.getByText("월")).toBeTruthy();
  });

  it("표에 없는 코드는 그대로 둔다 — 지어내지 않는다", () => {
    render(
      <TableCell label="주기" items={PERIOD}>
        {9}
      </TableCell>,
    );

    expect(screen.getByText("9")).toBeTruthy();
  });

  it("items 가 없으면 값을 그대로 둔다", () => {
    render(<TableCell label="시각">{7}</TableCell>);

    expect(screen.getByText("7")).toBeTruthy();
  });
});
