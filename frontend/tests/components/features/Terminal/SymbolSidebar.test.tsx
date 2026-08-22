// @vitest-environment jsdom
//
// 이슈 #326 — 종목 사이드바(FR-006·FR-007). 3탭 전환·종목 클릭 시 `setSymbol` 호출·스크리너
// 빈 상태의 이유 문구를 검증한다. `contextActions`(쓰기 액션)를 목으로 스파이해, "클릭하면
// 문맥이 바뀐다"를 UI 클릭만으로 증명한다(개발자도구 훅 없이) — O6 이 임시로 하던 것을 이
// 오더가 진짜 UI 로 대체한다는 증명 의무의 단위 테스트 버전이다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SymbolSidebar } from "@/components/features/Terminal/SymbolSidebar";
import { setSymbol } from "@/stores/terminal/contextActions";
import { selectWatchlistList } from "@/services/watchlist/watchlistService";
import { selectHoldingList, selectPortfolioList } from "@/services/portfolio/portfolioService";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";
import type { HoldingOut, PortfolioOut } from "@/schemas/portfolio/portfolio";

vi.mock("@/stores/terminal/contextActions", () => ({
  setSymbol: vi.fn(),
}));

vi.mock("@/services/watchlist/watchlistService", () => ({
  selectWatchlistList: vi.fn(),
}));

vi.mock("@/services/portfolio/portfolioService", () => ({
  selectPortfolioList: vi.fn(),
  selectHoldingList: vi.fn(),
}));

const WATCHLIST_ROWS: WatchlistOut[] = [
  { ticker: "005930", issuer_nm: "삼성전자", market: "KOSPI", use_at: "Y" } as WatchlistOut,
  { ticker: "AAPL", issuer_nm: "Apple Inc.", market: "NASDAQ", use_at: "Y" } as WatchlistOut,
];

const PORTFOLIOS: PortfolioOut[] = [{ portfolio_id: "core", portfolio_nm: "코어", sort_ordr: 1, use_at: "Y" }];

const HOLDING_ROWS: HoldingOut[] = [
  { portfolio_id: "core", ticker: "005930", holding_nm: "삼성전자", quantity: 10, avg_price: 70000, use_at: "Y" },
];

function setup() {
  vi.mocked(selectWatchlistList).mockResolvedValue({ items: WATCHLIST_ROWS, total_count: WATCHLIST_ROWS.length });
  vi.mocked(selectPortfolioList).mockResolvedValue({ items: PORTFOLIOS, total_count: PORTFOLIOS.length });
  vi.mocked(selectHoldingList).mockResolvedValue({ items: HOLDING_ROWS, total_count: HOLDING_ROWS.length });
  return render(<SymbolSidebar />);
}

afterEach(() => {
  cleanup();
  vi.mocked(setSymbol).mockReset();
  vi.mocked(selectWatchlistList).mockReset();
  vi.mocked(selectPortfolioList).mockReset();
  vi.mocked(selectHoldingList).mockReset();
});

describe("SymbolSidebar — 탭 3개(FR-006)", () => {
  it("기본은 관심종목 탭이고, 실데이터 2건이 뜬다", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());
    expect(screen.getByText("AAPL")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "관심종목" })).toHaveProperty("ariaSelected", "true");
  });

  it("보유 탭을 클릭하면 포트폴리오를 가로질러 모은 보유종목이 뜬다", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    await user.click(screen.getByRole("tab", { name: "보유" }));

    await waitFor(() => expect(selectPortfolioList).toHaveBeenCalled());
    // HoldingTab 은 서버 실패와 정상 0건을 구분하려고 throwOnFailure 를 함께 넘긴다 —
    // 호출 시그니처가 늘어난 것뿐, 조회 자체(portfolio_id)는 그대로다.
    await waitFor(() =>
      expect(selectHoldingList).toHaveBeenCalledWith({ portfolio_id: "core" }, { throwOnFailure: true }),
    );
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());
  });

  it("스크리너 탭을 클릭하면 빈 화면이 아니라 이유가 뜬다(NFR-001)", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    await user.click(screen.getByRole("tab", { name: "스크리너" }));

    expect(
      await screen.findByText("스크리너 결과가 아직 제공되지 않습니다 — 스크리너 테이블과 서비스가 아직 없습니다."),
    ).toBeTruthy();
  });

  it("ArrowRight/ArrowLeft 로 탭 사이를 키보드만으로 오간다", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    screen.getByRole("tab", { name: "관심종목" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "보유" })).toHaveProperty("ariaSelected", "true");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "보유" }));

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "관심종목" })).toHaveProperty("ariaSelected", "true");
  });
});

describe("SymbolSidebar — 관심종목 200건 상한(#326 교차 리뷰 지적, 조용한 절단 금지)", () => {
  it("201건 이상이면 절단 사실을 표시한다", async () => {
    const manyRows: WatchlistOut[] = Array.from({ length: 205 }, (_, i) => ({
      ticker: `T${i}`,
      issuer_nm: `종목${i}`,
      market: "KOSPI",
      use_at: "Y",
    })) as WatchlistOut[];
    vi.mocked(selectWatchlistList).mockResolvedValue({ items: manyRows, total_count: manyRows.length });
    render(<SymbolSidebar />);

    expect(await screen.findByText("205건 중 200건 표시")).toBeTruthy();
  });

  it("200건 이하면 절단 표시가 뜨지 않는다", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    expect(screen.queryByText(/건 중.*건 표시/)).toBeNull();
  });
});

describe("SymbolSidebar — 종목 클릭 → setSymbol(FR-006, 룰 14)", () => {
  it("관심종목 행을 클릭하면 그 종목으로 setSymbol 이 호출된다", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    await user.click(screen.getByText("005930"));

    expect(setSymbol).toHaveBeenCalledWith({ ticker: "005930", market: "KOSPI", name: "삼성전자" });
  });

  it("보유 행을 클릭하면 market 을 지어내지 않고 빈 문자열로 넘긴다(백엔드에 그 컬럼이 없다)", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());
    await user.click(screen.getByRole("tab", { name: "보유" }));
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    await user.click(screen.getByText("005930"));

    expect(setSymbol).toHaveBeenCalledWith({ ticker: "005930", market: "", name: "삼성전자" });
  });
});
