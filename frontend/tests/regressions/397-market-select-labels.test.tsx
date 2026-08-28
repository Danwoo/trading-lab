// @vitest-environment jsdom
//
// #397 — 격자 폼의 「시장」 드롭다운이 빈 줄 여섯 개로 열리고, 고르면 시장이 지워졌다.
//
// 원인은 `SelectBox` 에 `{value,label}` 객체를 주면서 `displayExpr`/`valueExpr` 를 안 준 것 —
// 기본값 `code_nm`/`code` 가 항목에 없어 표시는 "" 이고 값은 `undefined` 였다. 화면은 멀쩡한 듯
// 서 있고 콘솔 경고(`same key`)만 쌓여 아무도 못 봤다.
//
// 두 층으로 잡는다:
//   ① 폼 — 시장 여섯이 이름으로 열리고, 고른 것이 `market` 값으로 올라간다 (이 결함의 재현).
//   ② 프리미티브 — 객체 항목이 expr 키를 안 가지면 `SelectMenu` 가 빈 줄을 그리지 않고 던진다
//      (같은 클래스의 다음 호출부를 잡는 그물 — 어느 화면이든 렌더 순간 실패한다).
//
// 배치: 폼 + 프리미티브를 관통하는 회귀라 tests/regressions/ 에 둔다.

import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import { SelectBox } from "@/components/shared/ui/SelectBox";
import { assertItemsMatchExprs } from "@/components/shared/ui/primitives/SelectMenu";
import type { GridRunFormController, GridRunFormState } from "@/hooks/bench/useGridRunForm";

afterEach(cleanup);

// 이슈가 적은 기대 그대로 — bar 라우터가 받는 시장 목록(backend-service/app/routers/bar/bar_router.py).
const EXPECTED_MARKETS = ["KOSPI", "KOSDAQ", "KONEX", "NASDAQ", "NYSE", "AMEX"];

const FORM: GridRunFormState = {
  market: "KOSPI",
  symbol: "005930",
  period_from: "2023-08-21",
  period_to: "2026-08-20",
  initial_cash: 10_000_000,
};

function renderForm() {
  const changed: Array<[string, unknown]> = [];

  function Harness() {
    const [form, setForm] = useState<GridRunFormState>(FORM);
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
    return <GridRunForm bots={[]} controller={controller} isRunning={false} onRun={vi.fn()} />;
  }

  render(<Harness />);
  // 트리거 버튼은 `<label>` 안에 있어 라벨로 찾는다 — 라벨 글자에 버튼 글자가 따라붙으므로 앞에서 건다.
  const marketTrigger = () => screen.getByLabelText("시장", { exact: false }) as HTMLButtonElement;
  const valuesOf = (fieldName: string) => changed.filter(([name]) => name === fieldName).map(([, value]) => value);
  return { marketTrigger, valuesOf };
}

describe("#397 ① — 시장 드롭다운은 이름으로 열리고 고른 것이 값이 된다", () => {
  it("여섯 시장이 전부 이름을 갖고 열린다 — 빈 줄은 하나도 없다", async () => {
    const user = userEvent.setup();
    const { marketTrigger } = renderForm();

    await user.click(marketTrigger());
    const options = within(screen.getByRole("listbox")).getAllByRole("option");
    const labels = options.map((option) => option.textContent?.replace("✓", "").trim());

    // fail-closed — 몇 줄을 봤는지 남긴다. 0건이면 아래 등식이 곧바로 깨진다.
    console.log(`#397 시장 드롭다운 검사: ${labels.length}줄 — ${labels.join(", ")}`);
    expect(labels).toEqual(EXPECTED_MARKETS);
  });

  it("고른 시장이 값으로 올라가고 버튼에 그대로 보인다 — 지워지지 않는다", async () => {
    const user = userEvent.setup();
    const { marketTrigger, valuesOf } = renderForm();

    await user.click(marketTrigger());
    await user.click(screen.getByRole("option", { name: "KOSDAQ" }));

    expect(valuesOf("market")).toEqual(["KOSDAQ"]);
    expect(marketTrigger().textContent).toContain("KOSDAQ");
    expect(screen.queryByText("-- 선택 --")).toBeNull();
  });
});

describe("#397 ② — 객체 항목이 expr 키를 안 가지면 SelectMenu 는 빈 줄 대신 던진다", () => {
  it("#397 의 모양(`{value,label}` + 기본 expr)은 렌더 순간 실패한다", () => {
    const items = ["KOSPI", "KOSDAQ"].map((value) => ({ value, label: value }));
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<SelectBox fieldName="market" value="KOSPI" items={items} onValueChanged={vi.fn()} />)).toThrow(
      /"code"·"code_nm" 키가 없습니다/,
    );
    vi.restoreAllMocks();
  });

  it("에러는 빠진 키와 항목의 실제 키를 함께 말한다 — 어느 호출부인지 바로 짚게", () => {
    expect(() => assertItemsMatchExprs([{ value: "A", label: "a" }], "label", "id")).toThrow(
      'SelectMenu: 항목에 "id" 키가 없습니다 — displayExpr="label", valueExpr="id" 인데 항목 키는 [value, label] 입니다.',
    );
  });

  it.each<[string, any[], string, string]>([
    ["expr 이 항목 키와 맞는 객체", [{ code: "A", code_nm: "a" }], "code_nm", "code"],
    ["값이 null 이라도 키는 있는 객체", [{ code: null, code_nm: null }], "code_nm", "code"],
    ["문자열 배열", ["KOSPI", "KOSDAQ"], "code_nm", "code"],
    ["숫자 배열", [1, 2, 3], "code_nm", "code"],
    ["빈 목록", [], "code_nm", "code"],
    ["null 항목이 섞인 목록", [null, { code: "A", code_nm: "a" }], "code_nm", "code"],
  ])("%s 은 던지지 않는다", (_label, items, displayExpr, valueExpr) => {
    expect(() => assertItemsMatchExprs(items, displayExpr, valueExpr)).not.toThrow();
  });
});
