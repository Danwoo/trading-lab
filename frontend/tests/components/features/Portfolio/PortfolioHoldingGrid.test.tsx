// @vitest-environment jsdom
//
// #356 — 보유종목 관리 그리드에 `market` 입력이 없어 신규 등록 시에도 값을 채울 방법이 없었다.
// 컬럼은 이미 있었고(alembic 0010, backend Holding.market, HoldingSchema.market) UI 만 없었다.
// 터미널은 "시장을 채우면 이 패널이 열립니다"라고 안내하는데 채울 자리가 없던 상태다.
//
// 이 파일이 보는 것:
//   ① 그리드 컬럼 집합에 market 이 있고, **관심종목과 같은 코드 그룹(5000)** 을 룩업으로 쓴다
//      — 두 화면이 다른 목록을 쓰면 같은 종목의 시장이 화면마다 달라진다.
//   ② 등록/수정 폼에 시장 입력이 있고, 고른 값이 `market` 필드로 상위에 전달된다
//      (여기가 없으면 신규 행도 계속 NULL 이다).
//
// **검증 경계 (#391 의 교훈)** — jsdom 에는 레이아웃·CSS 가 없다. 그래서 이 테스트는 "필드가
// 트리에 있고 올바른 목록에 배선돼 값이 위로 전달된다"까지만 증명한다. **눈에 보이는지·
// 배치가 맞는지·다른 요소에 가려지지 않는지는 증명하지 않는다.** 그 축은 사람의 화면 확인이다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PortfolioHoldingGrid from "@/components/features/Portfolio/PortfolioHoldingGrid";
import type { Holding } from "@/schemas/portfolio/portfolio";

// WatchlistContainer.test.tsx 와 같은 이유 — 공용 배럴이 env.ts(t3-oss 검증)까지 끌고 온다.
vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

vi.mock("@/services/portfolio/portfolioService", () => ({
  selectHoldingList: vi.fn(async () => ({ items: [], total_count: 0 })),
  createHolding: vi.fn(),
  updateHolding: vi.fn(),
  deleteHolding: vi.fn(),
}));

// DetailGridPanel 자체는 이 테스트의 관심사가 아니다 — 넘겨받는 props(컬럼·폼 컴포넌트)를
// 그대로 꺼내 검사한다. 이렇게 해야 그리드 커널 구현이 바뀌어도 이 그물이 흔들리지 않는다.
let panelProps: any = null;
vi.mock("@/components/shared/DataPanel", () => ({
  DetailGridPanel: (props: any) => {
    panelProps = props;
    return <div data-testid="detail-grid-panel" />;
  },
}));

// PortfolioContainer 가 만드는 codeList 와 같은 모양 (getCode("5000") — prisma/init/seed.sql).
const MARKET_CODES = [
  { code: "KOSPI", code_nm: "KOSPI" },
  { code: "KOSDAQ", code_nm: "KOSDAQ" },
  { code: "NASDAQ", code_nm: "NASDAQ" },
  { code: "NYSE", code_nm: "NYSE" },
];
const CODE_LIST = { useAt: [{ code: "Y", code_nm: "사용" }], market: MARKET_CODES };

function renderGrid() {
  panelProps = null;
  render(<PortfolioHoldingGrid portfolioId="P1" codeList={CODE_LIST} editable />);
  expect(panelProps, "DetailGridPanel 이 렌더되지 않았다").toBeTruthy();
  return panelProps;
}

afterEach(cleanup);

describe("#356 보유종목 그리드 — market 컬럼", () => {
  it("컬럼 집합에 market 이 있다", () => {
    const fields = renderGrid().columns.map((c: any) => c.dataField);
    expect(fields).toContain("market");
  });

  it("market 컬럼은 관심종목과 같은 코드 목록을 룩업으로 쓴다 (필터 행도 표시명 드롭다운이 된다)", () => {
    const market = renderGrid().columns.find((c: any) => c.dataField === "market");
    expect(market.lookup).toEqual({
      dataSource: MARKET_CODES,
      displayExpr: "code_nm",
      valueExpr: "code",
    });
  });
});

describe("#356 보유종목 등록/수정 폼 — market 입력", () => {
  function renderForm(formData: Partial<Holding>, onFieldChange = vi.fn()) {
    const { FormComponent, formProps } = renderGrid();
    cleanup();
    render(
      <FormComponent
        formData={formData}
        modalMode="create"
        onFieldChange={onFieldChange}
        getFieldProps={() => ({})}
        {...formProps}
      />,
    );
    return onFieldChange;
  }

  /** 라벨 "시장" 셀의 다음 형제 = 그 필드의 내용 셀 (TableCell 의 렌더 구조). */
  function marketContentCell(): HTMLElement {
    const labelCell = screen.getByText("시장").closest("td, div") as HTMLElement;
    const content = labelCell?.nextElementSibling as HTMLElement;
    expect(content, "시장 라벨 옆의 내용 셀을 찾지 못했다").toBeTruthy();
    return content;
  }

  it("시장 입력이 폼에 있다", () => {
    renderForm({ use_at: "Y" });
    expect(screen.getByText("시장")).toBeTruthy();
  });

  it("기존 값이 있으면 그 값을 보여준다 (수정 시 값이 사라지지 않는다)", () => {
    renderForm({ use_at: "Y", market: "NASDAQ" });
    // 닫힌 드롭다운은 고른 값의 **표시명**을 트리거 버튼에 그린다(#341 SelectMenu).
    expect(marketContentCell().textContent).toContain("NASDAQ");
  });

  it("목록에서 고른 값이 market 필드로 상위에 전달된다 (신규 행이 NULL 로 남지 않는다)", async () => {
    const onFieldChange = renderForm({ use_at: "Y" });
    const user = userEvent.setup();

    // 시장 셀 안의 드롭다운만 연다 — 사용여부 SelectBox 와 섞이지 않게 라벨 셀을 기준으로 찾는다.
    // TableCell 은 라벨과 내용을 **형제** 셀로 그린다(라벨 td 다음이 내용 td).
    const trigger = marketContentCell().querySelector('[aria-haspopup="listbox"]') as HTMLElement;
    expect(trigger, "시장 드롭다운 트리거를 찾지 못했다").toBeTruthy();

    await user.click(trigger);
    const option = await screen.findByText("KOSDAQ");
    await user.click(option);

    expect(onFieldChange).toHaveBeenCalledWith("market", "KOSDAQ");
  });

  it("선택을 지울 수 있다 — 시장은 선택 필드다(스키마 Optional·기존 행 미백필)", async () => {
    const onFieldChange = renderForm({ use_at: "Y", market: "NASDAQ" });
    const clear = marketContentCell().querySelector('[aria-label="선택 지우기"]') as HTMLElement;
    expect(clear, "지우기 버튼이 없다").toBeTruthy();

    await userEvent.setup().click(clear);
    expect(onFieldChange).toHaveBeenCalledWith("market", null);
  });
});
