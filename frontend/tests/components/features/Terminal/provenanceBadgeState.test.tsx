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
//
// #284 — 그 축이 둘(`not-chosen` ∪ 나머지 전부)뿐이라 **나머지가 다시 뭉갰다**: 「아직 실행
// 안 함」인 `/bench` 격자 자리에 「제공 안 됨」이 붙었는데 바로 아래에는 동작하는 실행 폼이
// 있었다. 그래서 축을 상태별로 펴고 `because` 를 생략 불가로 바꿨다 — 아래 표가 전수다.
// #227 의 단언은 그대로 살아 있다(`no-source` 는 종전대로 「제공 안 됨」).

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { ProvenanceBadge } from "@/components/features/Terminal/ProvenanceBadge";
import type { UnavailableBecause } from "@/types/terminal/provenance";

/** `because` 전수 — 하나가 늘면 이 표가 컴파일에서 깨진다(`Record`). */
const LABELS: Record<UnavailableBecause, string> = {
  "not-chosen": "고르면 채워집니다",
  checking: "확인 중",
  "not-run": "아직 실행 안 함",
  "run-failed": "실행 실패",
  empty: "대상 없음",
  unreadable: "못 읽음",
  "no-source": "제공 안 됨",
};

afterEach(cleanup);

describe("#227 · #284 「제공 안 됨」 배지의 상태 구분", () => {
  it("아직 고르지 않았으면 다음 걸음을 말한다", () => {
    render(
      <ProvenanceBadge provenance={{ kind: "unavailable", reason: "선택된 종목이 없습니다", because: "not-chosen" }} />,
    );

    expect(screen.getByText("고르면 채워집니다")).toBeTruthy();
    expect(screen.queryByText("제공 안 됨")).toBeNull();
  });

  it("정말 못 주는 것은 종전대로 「제공 안 됨」이다", () => {
    render(
      <ProvenanceBadge
        provenance={{ kind: "unavailable", reason: "이 시장의 소스가 없습니다", because: "no-source" }}
      />,
    );

    expect(screen.getByText("제공 안 됨")).toBeTruthy();
  });

  it.each(Object.entries(LABELS))("`%s` 는 「%s」라 부른다", (because, label) => {
    render(
      <ProvenanceBadge provenance={{ kind: "unavailable", reason: "사유", because: because as UnavailableBecause }} />,
    );

    expect(screen.getByText(label)).toBeTruthy();
  });

  it("동작하는 자리(아직 실행 안 함·못 읽음)를 「제공 안 됨」이라 부르지 않는다", () => {
    for (const because of ["not-run", "run-failed", "unreadable", "empty", "checking"] as UnavailableBecause[]) {
      cleanup();
      render(<ProvenanceBadge provenance={{ kind: "unavailable", reason: "사유", because }} />);
      expect(screen.queryByText("제공 안 됨"), `${because} 가 「제공 안 됨」으로 뭉개졌다`).toBeNull();
    }
  });

  it("라벨이 서로 겹치지 않는다 — 두 상태가 같은 말을 하면 가른 뜻이 없다", () => {
    const labels = Object.values(LABELS);
    expect(new Set(labels).size).toBe(labels.length);
  });
});
