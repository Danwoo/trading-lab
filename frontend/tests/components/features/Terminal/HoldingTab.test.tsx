// @vitest-environment jsdom
//
// 두 결함의 회귀 그물 — ① 서버 실패가 "데이터 없음"으로 보임 ② 같은 종목이 여러 포트폴리오에
// 있으면 중복 표시.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { HoldingTab } from "@/components/features/Terminal/HoldingTab";
import { selectHoldingList, selectPortfolioList } from "@/services/portfolio/portfolioService";
import { ApiCallFailure } from "@/utils/common/api/client";
import type { HoldingOut, PortfolioOut } from "@/schemas/portfolio/portfolio";

vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

vi.mock("@/hooks/terminal/useQuoteBatch", () => ({
  useQuoteBatch: () => ({ quotes: {}, provenance: "unavailable" }),
}));

vi.mock("@/services/portfolio/portfolioService", () => ({
  selectPortfolioList: vi.fn(),
  selectHoldingList: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.mocked(selectPortfolioList).mockReset();
  vi.mocked(selectHoldingList).mockReset();
});

const PORTFOLIOS: PortfolioOut[] = [
  { portfolio_id: "core", portfolio_nm: "코어", sort_ordr: 1, use_at: "Y" },
  { portfolio_id: "growth", portfolio_nm: "성장", sort_ordr: 2, use_at: "Y" },
];

describe("HoldingTab — 서버 실패와 정상 0건 구분", () => {
  it("포트폴리오 조회가 서버 실패(success:false → throwOnFailure 로 예외)면 '불러오지 못했습니다'를 보여준다 — 빈 상태 문구가 아니다", async () => {
    vi.mocked(selectPortfolioList).mockRejectedValue(new ApiCallFailure());

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);

    expect(await screen.findByText("보유종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.")).toBeTruthy();
    expect(screen.queryByText("보유종목이 없습니다 — 포트폴리오 화면에서 먼저 등록하세요.")).toBeNull();
  });

  it("보유 조회가 서버 실패면 '불러오지 못했습니다'를 보여준다", async () => {
    vi.mocked(selectPortfolioList).mockResolvedValue({ items: PORTFOLIOS, total_count: PORTFOLIOS.length });
    vi.mocked(selectHoldingList).mockRejectedValue(new ApiCallFailure());

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);

    expect(await screen.findByText("보유종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.")).toBeTruthy();
  });

  it("정상 응답인데 보유가 0건이면 '없습니다'를 보여준다 — 실패와 다른 문구", async () => {
    vi.mocked(selectPortfolioList).mockResolvedValue({ items: [], total_count: 0 });

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);

    expect(await screen.findByText("보유종목이 없습니다 — 포트폴리오 화면에서 먼저 등록하세요.")).toBeTruthy();
    expect(screen.queryByText("보유종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.")).toBeNull();
  });

  it("두 서비스 함수 모두 throwOnFailure: true 로 호출한다 — 이 계약이 빠지면 위 테스트들이 다시 실패로 돌아간다", async () => {
    vi.mocked(selectPortfolioList).mockResolvedValue({ items: PORTFOLIOS, total_count: PORTFOLIOS.length });
    vi.mocked(selectHoldingList).mockResolvedValue({ items: [], total_count: 0 });

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);
    await waitFor(() => expect(selectHoldingList).toHaveBeenCalled());

    expect(selectPortfolioList).toHaveBeenCalledWith({}, { throwOnFailure: true });
    expect(selectHoldingList).toHaveBeenCalledWith({ portfolio_id: "core" }, { throwOnFailure: true });
    expect(selectHoldingList).toHaveBeenCalledWith({ portfolio_id: "growth" }, { throwOnFailure: true });
  });
});

describe("HoldingTab — 같은 종목이 여러 포트폴리오에 있으면 중복 표시되지 않는다", () => {
  it("삼성전자를 core·growth 둘 다 보유해도 사이드바엔 한 번만 뜬다", async () => {
    vi.mocked(selectPortfolioList).mockResolvedValue({ items: PORTFOLIOS, total_count: PORTFOLIOS.length });
    vi.mocked(selectHoldingList).mockImplementation(async (params: { portfolio_id: string }) => {
      const holding: HoldingOut = {
        portfolio_id: params.portfolio_id,
        ticker: "005930",
        holding_nm: "삼성전자",
        quantity: 10,
        avg_price: 70000,
        use_at: "Y",
      };
      return { items: [holding], total_count: 1 };
    });

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);

    await waitFor(() => expect(screen.getAllByText("삼성전자")).toHaveLength(1));
    expect(screen.getAllByText("005930")).toHaveLength(1);
  });

  it("서로 다른 종목은 그대로 둘 다 보여준다 — 중복 제거가 과해서 진짜 다른 보유를 지우지 않는다", async () => {
    vi.mocked(selectPortfolioList).mockResolvedValue({
      items: [PORTFOLIOS[0]],
      total_count: 1,
    });
    vi.mocked(selectHoldingList).mockResolvedValue({
      items: [
        { portfolio_id: "core", ticker: "005930", holding_nm: "삼성전자", quantity: 10, avg_price: 70000, use_at: "Y" },
        { portfolio_id: "core", ticker: "AAPL", holding_nm: "Apple Inc.", quantity: 5, avg_price: 150, use_at: "Y" },
      ],
      total_count: 2,
    });

    render(<HoldingTab activeTicker={undefined} onSelect={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());
    expect(screen.getByText("AAPL")).toBeTruthy();
  });
});
