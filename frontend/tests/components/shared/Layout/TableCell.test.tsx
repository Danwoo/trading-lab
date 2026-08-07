// @vitest-environment jsdom
//
// #303 리뷰 지적 — 관리 상세 화면 5곳(AdminUser·Author·Menu·Workspace·Code)이 `TableCell` 로
// reg_dt/mod_dt 를 그리는데, 그 경로는 formatDateTime() 제거 이후 인스턴트(ISO, UTC) 를 그대로
// 받으면서도 `dataType` 을 넘기지 않아 **기본값 "string"** 으로 떨어져 원문 ISO 를 그대로
// 출력하고 있었다 — 그리드는 고쳤는데 상세 화면에서 같은 결함이 반대 방향으로 남았던 사례.
//
// `dataType="datetime"` 을 넘기면 `TableCell` 이 공용 포맷터 `formatDate()`(#263 정책, 표시
// 타임존 = 사용자 타임존)를 타야 한다 — 두 벌 포맷터를 만들지 않는다는 리뷰 요구의 증거.
//
// 이 레포는 `@testing-library/jest-dom` 을 안 쓴다(package.json 미의존) — 다른 컴포넌트
// 테스트(WatchlistContainer.test.tsx)와 같이 `.toBeTruthy()`/`.toBeNull()` 로 존재를 확인한다.

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { TableCell } from "@/components/shared/Layout/TableCell";
import { formatDate } from "@/utils/common/formatters/date";

afterEach(cleanup);

// table 모드가 기본이라 <td> 를 낸다 — 유효한 테이블 트리 안에서 렌더한다.
const renderCell = (children: React.ReactNode, props: Partial<React.ComponentProps<typeof TableCell>> = {}) =>
  render(
    <table>
      <tbody>
        <tr>
          <TableCell {...props}>{children}</TableCell>
        </tr>
      </tbody>
    </table>,
  );

// 실제 API 가 보내는 전선 위 값(#303 이후 — 인스턴트 그대로, ISO+Z)
const WIRE = "2026-07-30T01:00:00.000Z";

describe('TableCell — dataType="datetime" (#303 상세 화면 보강)', () => {
  it('dataType="datetime" 을 넘기면 formatDate() 와 정확히 같은 문자열을 그린다 (공용 포맷터 단일화)', () => {
    renderCell(WIRE, { dataType: "datetime" });
    const expected = formatDate(WIRE, "datetime")!;
    expect(screen.getByText(expected)).toBeTruthy();
    // 원문 ISO 가 그대로 나오지 않는다는 것도 명시적으로 확인 — 이게 리뷰가 잡은 회귀다.
    expect(screen.queryByText(WIRE)).toBeNull();
  });

  it("부정 통제 — dataType 을 생략하면(기본값 string) 원문 ISO 가 그대로 노출된다", () => {
    // 리뷰가 지적한 5곳이 고치기 전에 실제로 이랬다 — dataType 을 빼면 지금도 이렇다는 것을
    // 증명해, 5곳에 dataType="datetime" 을 넘긴 것이 회귀를 실제로 막는지 확인한다.
    renderCell(WIRE);
    expect(screen.getByText(WIRE)).toBeTruthy();
  });

  it('dataType="date" 도 formatDate() 와 일치한다', () => {
    renderCell(WIRE, { dataType: "date" });
    expect(screen.getByText(formatDate(WIRE, "date")!)).toBeTruthy();
  });
});

describe("TableCell — 기본값(string) 회귀 없음 (블라스트 반경 확인)", () => {
  // datetime/date 분기만 고쳤다 — 기본값(string)과 number/boolean 분기는 손대지 않았다.
  // 문자열 컬럼이 날짜처럼 파싱되거나 포맷이 바뀌면 안 된다.
  it.each([
    ["일반 문자열", "관리자", "관리자"],
    ["숫자로 보이는 문자열", "12345", "12345"],
  ])("%s 은 그대로 렌더한다", (_label, input, expected) => {
    renderCell(input);
    expect(screen.getByText(expected)).toBeTruthy();
  });

  it("빈 문자열은 nbsp 로 빈 셀 처리된다 (기존 동작 보존)", () => {
    renderCell("");
    expect(screen.getByRole("cell").textContent).toBe(" ");
  });

  it("number 타입 + 패턴은 그대로 동작한다 (date/datetime 리팩터와 무관, 기존 동작 그대로)", () => {
    renderCell("1234.5", { dataType: "number", format: "#,##0" });
    // TableCell 의 "#,##0" 분기는 반올림이 아니라 toLocaleString() 위임이다(리팩터 전과 동일).
    expect(screen.getByText("1,234.5")).toBeTruthy();
  });

  it("null/undefined 는 여전히 nbsp 로 빈 셀 처리된다", () => {
    renderCell(null, { dataType: "datetime" });
    expect(screen.getByRole("cell").textContent).toBe(" ");
  });
});
