// @vitest-environment jsdom
//
// #227 — **「아직 안 골랐다」와 「못 준다」를 배지가 갈라 말한다.**
//
// 첫 진입의 터미널은 차트·종목 정보·호가가 모두 「제공 안 됨」이었다. 실제로는 아직 종목을
// 고르지 않았을 뿐인데, 회색 「제공 안 됨」이 화면을 덮으면 제품이 고장 난 것처럼 보인다.
// 실측: `/terminal` 첫 화면에 「제공 안 됨」이 3회.
//
// 문구가 아니라 `because` 축으로 가른다 — 문구를 보고 가르면 문구만 바뀌어도 판정이
// 조용히 갈린다.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ProvenanceBadge } from "@/components/features/Terminal/ProvenanceBadge";

describe("#227 제공 안 됨 배지의 상태 구분", () => {
  it("아직 고르지 않았으면 다음 걸음을 말한다", () => {
    render(
      <ProvenanceBadge provenance={{ kind: "unavailable", reason: "선택된 종목이 없습니다", because: "not-chosen" }} />,
    );

    expect(screen.getByText("고르면 채워집니다")).toBeTruthy();
    expect(screen.queryByText("제공 안 됨")).toBeNull();
  });

  it("정말 못 주는 것은 종전대로 「제공 안 됨」이다", () => {
    render(<ProvenanceBadge provenance={{ kind: "unavailable", reason: "이 시장의 소스가 없습니다" }} />);

    expect(screen.getByText("제공 안 됨")).toBeTruthy();
  });
});
