// @vitest-environment jsdom
//
// 이슈 #318 — 시세 패널 안에서 종목을 찾아 담는다. 이 파일이 지는 회귀는 넷이다:
//
//   ① 이름으로 찾는다 — 사용자는 「삼성전자」를 알지 「005930」을 모른다
//   ② 4,303행을 한 번에 요청하지 않는다 (조회 상한을 붙여 부른다)
//   ③ 「못 읽음」·「아직 안 받음」·「없음」이 서로 다른 문구를 낸다 (셋을 뭉개면 사용자가
//      자기가 친 종목명을 의심한다)
//   ④ 고르면 관심종목에 담기고 그 종목으로 문맥이 옮겨 간다
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SymbolSearch } from "@/components/features/Terminal/SymbolSearch";
import { selectInstrumentList } from "@/services/terminal/instrumentService";
import { createWatchlist } from "@/services/watchlist/watchlistService";
import type { InstrumentOut } from "@/schemas/terminal/instrument";

vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

vi.mock("@/services/terminal/instrumentService", () => ({
  selectInstrumentList: vi.fn(),
}));

vi.mock("@/services/watchlist/watchlistService", () => ({
  createWatchlist: vi.fn(),
}));

const SAMSUNG: InstrumentOut = {
  country: "KR",
  market: "KOSPI",
  symbol: "005930",
  issuer_nm: "삼성전자",
  currency: "KRW",
  is_active: "Y",
};

const MASTER_EMPTY_REASON = "종목 마스터를 아직 한 번도 받지 않았습니다 — 「적재」에서 종목 마스터를 먼저 받아 오세요.";

afterEach(() => {
  cleanup();
  vi.mocked(selectInstrumentList).mockReset();
  vi.mocked(createWatchlist).mockReset();
});

describe("SymbolSearch — 이름으로 찾아 담는다 (#318)", () => {
  it("종목명을 치면 그 말로 마스터를 훑고 결과를 보여준다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [], total_count: 0, unavailable_reason: null });
    render(<SymbolSearch onAdded={vi.fn()} />);
    await waitFor(() => expect(selectInstrumentList).toHaveBeenCalled());

    vi.mocked(selectInstrumentList).mockResolvedValue({
      items: [SAMSUNG],
      total_count: 1,
      unavailable_reason: null,
    });
    await userEvent.type(screen.getByLabelText("종목 검색"), "삼성전자");

    expect(await screen.findByText("삼성전자")).toBeTruthy();
    expect(screen.getByText("KOSPI · 005930")).toBeTruthy();
    await waitFor(() =>
      expect(vi.mocked(selectInstrumentList).mock.calls.at(-1)?.[0]).toEqual({ q: "삼성전자", take: 20 }),
    );
  });

  it("4,303행을 한 번에 요청하지 않는다 — 첫 조회부터 상한을 붙인다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [], total_count: 0, unavailable_reason: null });
    render(<SymbolSearch onAdded={vi.fn()} />);

    await waitFor(() => expect(selectInstrumentList).toHaveBeenCalled());
    const params = vi.mocked(selectInstrumentList).mock.calls[0][0];
    expect(typeof params.take).toBe("number");
    expect(params.take).toBeLessThanOrEqual(100);
  });

  it("상한에 걸려 잘렸으면 조용히 자르지 않고 전체 건수를 밝힌다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({
      items: [SAMSUNG],
      total_count: 300,
      unavailable_reason: null,
    });
    render(<SymbolSearch onAdded={vi.fn()} />);

    expect(await screen.findByText("300건 중 1건 표시 — 검색어를 좁히세요")).toBeTruthy();
  });
});

describe("SymbolSearch — 빈 자리가 왜 비었는지 갈라 말한다 (FR-021)", () => {
  it("마스터를 아직 안 받았으면 서버가 준 사유와 다음 걸음을 그대로 보여준다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({
      items: [],
      total_count: 0,
      unavailable_reason: MASTER_EMPTY_REASON,
    });
    render(<SymbolSearch onAdded={vi.fn()} />);

    expect(await screen.findByText(MASTER_EMPTY_REASON)).toBeTruthy();
    expect(screen.queryByText("찾는 종목이 없습니다 — 종목명 일부나 코드로 다시 찾아보세요.")).toBeNull();
  });

  it("마스터는 찼는데 그 이름이 없으면 「없다」고 말한다 — 적재 안내를 하지 않는다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [], total_count: 0, unavailable_reason: null });
    render(<SymbolSearch onAdded={vi.fn()} />);

    expect(await screen.findByText("찾는 종목이 없습니다 — 종목명 일부나 코드로 다시 찾아보세요.")).toBeTruthy();
    expect(screen.queryByText(MASTER_EMPTY_REASON)).toBeNull();
  });

  it("서버 실패는 「불러오지 못했습니다」다 — 0건 문구로 뭉개지 않는다", async () => {
    vi.mocked(selectInstrumentList).mockRejectedValue(new Error("boom"));
    render(<SymbolSearch onAdded={vi.fn()} />);

    expect(await screen.findByText("종목 목록을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.")).toBeTruthy();
    expect(screen.queryByText("찾는 종목이 없습니다 — 종목명 일부나 코드로 다시 찾아보세요.")).toBeNull();
  });
});

describe("SymbolSearch — 고르면 담기고 그 종목으로 옮겨 간다", () => {
  it("종목명·시장·통화까지 담고 문맥을 그 종목으로 넘긴다 — 티커를 손으로 칠 일이 없다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [SAMSUNG], total_count: 1, unavailable_reason: null });
    vi.mocked(createWatchlist).mockResolvedValue({ data: { ticker: "005930" } } as any);
    const onAdded = vi.fn();
    render(<SymbolSearch onAdded={onAdded} />);

    await userEvent.click(await screen.findByText("삼성전자"));

    await waitFor(() =>
      expect(createWatchlist).toHaveBeenCalledWith({
        ticker: "005930",
        issuer_nm: "삼성전자",
        market: "KOSPI",
        currency: "KRW",
        use_at: "Y",
      }),
    );
    expect(onAdded).toHaveBeenCalledWith({ ticker: "005930", market: "KOSPI", name: "삼성전자" });
  });

  it("이미 담긴 종목(409)은 실패가 아니다 — 그대로 고른다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [SAMSUNG], total_count: 1, unavailable_reason: null });
    vi.mocked(createWatchlist).mockRejectedValue({ response: { status: 409, data: { detail: "이미 존재합니다." } } });
    const onAdded = vi.fn();
    render(<SymbolSearch onAdded={onAdded} />);

    await userEvent.click(await screen.findByText("삼성전자"));

    await waitFor(() => expect(onAdded).toHaveBeenCalledWith({ ticker: "005930", market: "KOSPI", name: "삼성전자" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("담기가 실패하면 사유를 그 자리에 남긴다 — 조용히 아무 일도 안 일어난 것처럼 두지 않는다", async () => {
    vi.mocked(selectInstrumentList).mockResolvedValue({ items: [SAMSUNG], total_count: 1, unavailable_reason: null });
    vi.mocked(createWatchlist).mockRejectedValue({ response: { status: 400, data: { detail: "담지 못했습니다." } } });
    const onAdded = vi.fn();
    render(<SymbolSearch onAdded={onAdded} />);

    await userEvent.click(await screen.findByText("삼성전자"));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("담지 못했습니다.")).toBeTruthy();
    expect(onAdded).not.toHaveBeenCalled();
  });
});
