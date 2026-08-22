// @vitest-environment jsdom
//
// 이슈 #318 — 관심종목 0건에서 첫 종목 하나를 넣는 일이 **터미널을 안 떠나고** 끝나야 한다.
// 종전에는 이 자리의 유일한 출구가 `/admin/watchlist` 링크였다(WatchlistTab.tsx:49) —
// 관리자 셸로 나가 티커를 손으로 쳐야 했고, 종목 마스터 4,303행은 쓰이지 않았다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WatchlistTab } from "@/components/features/Terminal/WatchlistTab";
import { selectWatchlistList, createWatchlist } from "@/services/watchlist/watchlistService";
import { selectInstrumentList } from "@/services/terminal/instrumentService";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";
import type { InstrumentOut } from "@/schemas/terminal/instrument";

vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

vi.mock("@/hooks/terminal/useQuoteBatch", () => ({
  useQuoteBatch: () => ({ quotes: {}, provenance: "unavailable" }),
}));

vi.mock("@/services/watchlist/watchlistService", () => ({
  selectWatchlistList: vi.fn(),
  createWatchlist: vi.fn(),
}));

vi.mock("@/services/terminal/instrumentService", () => ({
  selectInstrumentList: vi.fn(),
}));

const SAMSUNG: InstrumentOut = {
  country: "KR",
  market: "KOSPI",
  symbol: "005930",
  issuer_nm: "삼성전자",
  currency: "KRW",
  is_active: "Y",
};

const WATCHLIST_ROW = { ticker: "AAPL", issuer_nm: "Apple Inc.", market: "NASDAQ", use_at: "Y" } as WatchlistOut;

afterEach(() => {
  cleanup();
  vi.mocked(selectWatchlistList).mockReset();
  vi.mocked(createWatchlist).mockReset();
  vi.mocked(selectInstrumentList).mockReset();
});

describe("WatchlistTab — 첫 종목을 터미널 안에서 담는다 (#318)", () => {
  it("0건 상태의 출구가 관리자 페이지 링크가 아니다", async () => {
    vi.mocked(selectWatchlistList).mockResolvedValue({ items: [], total_count: 0 });

    render(<WatchlistTab activeTicker={undefined} onSelect={vi.fn()} />);

    const action = await screen.findByRole("button", { name: "종목 찾아 담기" });
    expect(action).toBeTruthy();
    expect(screen.queryByRole("link", { name: "관심종목 등록하러 가기" })).toBeNull();
    // `/admin` 으로 나가는 어떤 링크도 남지 않았는지 — 라벨만 바꾸고 목적지가 그대로면
    // 이 이슈는 안 닫힌다.
    expect(document.querySelectorAll('a[href^="/admin"]').length).toBe(0);
  });

  it("0건에서 종목을 골라 담으면 목록을 다시 읽고 그 종목으로 문맥이 옮겨 간다", async () => {
    vi.mocked(selectWatchlistList).mockResolvedValue({ items: [], total_count: 0 });
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [SAMSUNG], total_count: 1, unavailable_reason: null });
    vi.mocked(createWatchlist).mockResolvedValue({ data: { ticker: "005930" } } as any);
    const onSelect = vi.fn();

    render(<WatchlistTab activeTicker={undefined} onSelect={onSelect} />);

    await userEvent.click(await screen.findByRole("button", { name: "종목 찾아 담기" }));
    expect(await screen.findByLabelText("종목 검색")).toBeTruthy();

    await userEvent.click(await screen.findByText("삼성전자"));

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith({ ticker: "005930", market: "KOSPI", name: "삼성전자" }));
    // 담은 뒤 목록을 다시 읽는다 — 최초 1회 + 재조회 1회.
    await waitFor(() => expect(vi.mocked(selectWatchlistList).mock.calls.length).toBeGreaterThan(1));
  });

  it("이미 종목이 있어도 검색 자리가 열려 있다 — 두 번째 종목을 담으러 관리자로 나가지 않는다", async () => {
    vi.mocked(selectWatchlistList).mockResolvedValue({ items: [WATCHLIST_ROW], total_count: 1 });
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [SAMSUNG], total_count: 1, unavailable_reason: null });

    render(<WatchlistTab activeTicker={undefined} onSelect={vi.fn()} />);

    await userEvent.click(await screen.findByRole("button", { name: "종목 추가" }));
    expect(await screen.findByLabelText("종목 검색")).toBeTruthy();

    // 목록이 있는 상태에서는 돌아갈 자리가 있으므로 닫는 자리를 준다.
    await userEvent.click(screen.getByRole("button", { name: "닫기" }));
    expect(await screen.findByText("Apple Inc.")).toBeTruthy();
  });
});
