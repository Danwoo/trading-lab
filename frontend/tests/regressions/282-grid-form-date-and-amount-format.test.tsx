// @vitest-environment jsdom
//
// #282 · #283 — 격자 실행 폼이 날짜와 금액을 화면의 다른 자리와 같은 규칙으로 말하는가.
//
// 두 결함이 같은 폼·같은 프리미티브에 있어 한 파일로 잡는다:
//   #282 날짜 — `DateBox` 가 네이티브 `<input type="date">` 였다. 그 표시 형식은 브라우저·OS
//        로케일이 정해 앱이 못 정한다(`08/21/2023`). **jsdom 은 그 로케일 렌더링을 흉내내지
//        않으므로**(`input.value` 는 어느 쪽이든 `2023-08-21`) "보이는 글자"만으로는 이 회귀를
//        못 잡는다 — 그래서 **표시 형식을 브라우저가 정하는 컨트롤을 폼에 세우지 않는다**는
//        구조 불변식까지 함께 단언한다. 실제 로케일 표기는 브라우저 실측이 정본이다(PR 본문).
//   #283 금액 — 시작 자금이 `10000000` 이었다. 성과의 분모라 자릿수를 잘못 읽으면 결과 전체를
//        잘못 읽는다. 리포트(`RunReportView`)와 같은 `toLocaleString("ko-KR")` 규칙을 쓴다.
//
// 폼은 상태를 `useGridRunForm` 이 갖고 그리기만 하므로(§21.6), 여기서는 그 훅 자리에 같은 계약의
// 작은 상태 하니스를 끼운다 — 값이 올라가고 다시 내려오는 왕복까지 봐야 "값이 씹히는가"를 잡는다.
//
// 배치: 소스 하나가 아니라 폼 + 두 프리미티브를 관통하는 회귀라 tests/regressions/ 에 둔다.

import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import type { GridRunFormController, GridRunFormState } from "@/hooks/bench/useGridRunForm";

afterEach(cleanup);

const FORM: GridRunFormState = {
  market: "KOSPI",
  symbol: "005930",
  period_from: "2023-08-21",
  period_to: "2026-08-20",
  initial_cash: 10_000_000,
};

function renderForm(overrides: Partial<GridRunFormState> = {}) {
  const changed: Array<[string, unknown]> = [];

  function Harness() {
    const [form, setForm] = useState<GridRunFormState>({ ...FORM, ...overrides });
    const controller: GridRunFormController = {
      botId: null,
      strategy: null,
      botDetailError: null,
      form,
      axes: [],
      formError: null,
      comboCount: 0,
      changeBot: vi.fn(),
      changeField: (fieldName, value) => {
        changed.push([String(fieldName), value]);
        setForm((prev) => ({ ...prev, [fieldName]: value as never }));
      },
      toggleAxis: vi.fn(),
      changeAxisSteps: vi.fn(),
      buildInput: vi.fn(() => null),
    };
    return <GridRunForm bots={[]} controller={controller} isRunning={false} runError={null} onRun={vi.fn()} />;
  }

  render(<Harness />);
  const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
  const valuesOf = (fieldName: string) => changed.filter(([name]) => name === fieldName).map(([, value]) => value);
  return { field, valuesOf };
}

describe("#282 — 구간 입력의 표시 형식은 앱이 정한다", () => {
  it("두 날짜 칸이 값 계약과 같은 YYYY-MM-DD 를 그대로 보인다", () => {
    const { field } = renderForm();

    expect(field("구간 시작").value).toBe("2023-08-21");
    expect(field("구간 끝").value).toBe("2026-08-20");
  });

  it("사용자가 읽고 치는 칸이 네이티브 날짜 입력이 아니다", () => {
    const { field } = renderForm();

    // `type="date"` 는 표시 형식을 앱이 못 정한다 — 값을 보여 주는 칸이 그것이면 #282 의 재발이다.
    expect(field("구간 시작").type).toBe("text");
    expect(field("구간 끝").type).toBe("text");
    // 달력 팝업 앵커용 숨은 `type="date"` 는 showPicker() 가 있는 브라우저에서만 그려진다 —
    // jsdom 에는 showPicker 가 없어 여기서는 어떤 date 입력도 렌더되지 않는다.
    expect(document.querySelectorAll('input[type="date"]')).toHaveLength(0);
  });

  it("완성된 날짜만 값으로 올라간다 — 타이핑 도중의 조각은 계약을 깨지 않는다", async () => {
    const user = userEvent.setup();
    const { field, valuesOf } = renderForm({ period_from: "" });

    await user.type(field("구간 시작"), "2024-03-05");

    // 조각(`2`, `20`, `2024-0` …)은 한 번도 안 올라가고, 완성된 날짜만 올라간다.
    expect(valuesOf("period_from")).toEqual(["2024-03-05"]);
    // 타이핑 중에도 화면은 친 그대로를 보인다 — 값이 씹히면 사용자가 다시 친다.
    expect(field("구간 시작").value).toBe("2024-03-05");
  });

  it("달력에 없는 날짜는 값으로 올라가지 않는다", async () => {
    const user = userEvent.setup();
    const { field, valuesOf } = renderForm({ period_from: "" });

    await user.type(field("구간 시작"), "2026-02-31");

    expect(valuesOf("period_from")).toEqual([]);
  });
});

describe("#283 — 시작 자금은 자릿수가 읽히게 보인다", () => {
  it("천단위 구분과 단위를 함께 보이고, 라벨도 단위를 적는다", () => {
    const { field } = renderForm();

    expect(field("시작 자금 (원)").value).toBe("10,000,000원");
  });

  it("편집 중에는 구분 없는 원본을 보이고, 친 숫자가 그대로 올라간다", async () => {
    const user = userEvent.setup();
    const { field, valuesOf } = renderForm();

    await user.click(field("시작 자금 (원)"));
    // 포커스를 받는 순간 구분 기호가 빠진다 — 커서가 쉼표 위에서 튀지 않게.
    expect(field("시작 자금 (원)").value).toBe("10000000");

    await user.clear(field("시작 자금 (원)"));
    await user.type(field("시작 자금 (원)"), "5000000");
    expect(field("시작 자금 (원)").value).toBe("5000000");
    expect(valuesOf("initial_cash").at(-1)).toBe(5_000_000);

    // 포커스를 잃으면 올라간 값을 다시 묶어서 보인다.
    await user.tab();
    expect(field("시작 자금 (원)").value).toBe("5,000,000원");
  });
});
