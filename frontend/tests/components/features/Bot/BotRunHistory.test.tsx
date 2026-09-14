// @vitest-environment jsdom
//
// #232 — **봇을 저장한 다음 갈 곳이 화면에 있다.**
//
// 이슈의 표현: 「봇을 만들어 저장했다. 그다음에 뭘 할 수 있는지 모르겠다.」 실험대는
// 「만들고 검증하고 굴리는 자리」라고 말하는데 봇 화면에서 검증으로 가는 길이 없었다.
//
// 이 그물이 잠그는 것 셋: ① 이력이 없어도 다음 걸음을 말한다 ② 이력이 있으면 목록으로
// 보인다 ③ 검증으로 가는 길이 그 봇을 데리고 간다(`?bot=<id>`).
//
// **검증 경계** — 서비스 층을 세운다. 백엔드가 그 봇의 실행만 주는지(워크스페이스 격리)는
// 여기서 보지 않는다 — 그 축은 `backend-service/scripts/verify_backtest_run_persists.py` 다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { BotRunHistory } from "@/components/features/Bot/BotRunHistory";

const selectRuns = vi.fn();

vi.mock("@/services/backtest/backtestService", () => ({
  selectBacktestRunsByBot: (...args: unknown[]) => selectRuns(...args),
}));

afterEach(() => {
  cleanup();
  selectRuns.mockReset();
});

function aRun(runId: number, params: Record<string, unknown> = { period: 20 }) {
  return {
    run_id: runId,
    status: "succeeded",
    strategy_key: "pullback",
    params,
    universe_def: {},
    period_from: "2026-01-01",
    period_to: "2026-06-30",
    attempt_no: 1,
    parent_run_id: null,
    finished_dt: null,
  };
}

describe("#232 봇 상세의 검증 이력", () => {
  it("검증한 적이 없으면 다음 걸음을 말한다 — 빈 자리로 두지 않는다", async () => {
    selectRuns.mockResolvedValue({ items: [], total_count: 0 });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText(/아직 검증한 적이 없습니다/)).toBeTruthy());
  });

  it("이력이 있으면 실행이 목록으로 보인다", async () => {
    selectRuns.mockResolvedValue({ items: [aRun(11), aRun(12)], total_count: 2 });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText("#11")).toBeTruthy());
    expect(screen.getByText("#12")).toBeTruthy();
  });

  it("한 페이지만 보일 때 총수를 말한다 — 「이만큼이 전부」로 읽히지 않게", async () => {
    selectRuns.mockResolvedValue({ items: [aRun(11), aRun(12)], total_count: 37 });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText(/모두 37번 검증했습니다/)).toBeTruthy());
  });

  it("다 보일 때는 총수를 덧붙이지 않는다", async () => {
    selectRuns.mockResolvedValue({ items: [aRun(11)], total_count: 1 });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText("#11")).toBeTruthy());
    expect(screen.queryByText(/모두 .*번 검증했습니다/)).toBeNull();
  });

  it("검증하러 가는 길이 그 봇을 데리고 간다", async () => {
    selectRuns.mockResolvedValue({ items: [], total_count: 0 });

    render(<BotRunHistory botId={42} />);

    const link = await screen.findByText("이 봇으로 검증하러 가기");
    expect(link.getAttribute("href")).toBe("/bench?bot=42");
  });

  it("조회한 봇 번호를 그대로 묻는다", async () => {
    selectRuns.mockResolvedValue({ items: [], total_count: 0 });

    render(<BotRunHistory botId={99} />);

    await waitFor(() => expect(selectRuns).toHaveBeenCalledWith(99));
  });

  it("못 읽었으면 「0건」으로 뭉개지 않는다", async () => {
    selectRuns.mockRejectedValue(new Error("이력을 읽지 못했습니다"));

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText(/이력을 불러오지 못했습니다/)).toBeTruthy());
    expect(screen.queryByText(/아직 검증한 적이 없습니다/)).toBeNull();
  });
});

// F13 — 같은 조합을 다시 돌리면 새 행이 생긴다(실측: 한 조합이 25행). 목록이 조합을 보이고
// 반복임을 말해야 「이 봇을 500번 검증했다」가 무엇을 뜻하는지 읽힌다.
describe("F13 이력에서 조합이 보이고 반복이 드러난다", () => {
  it("각 줄이 돌린 조합을 격자와 같은 어휘로 보인다", async () => {
    selectRuns.mockResolvedValue({ items: [aRun(11, { ma_period: 120, pullback_pct: 15 })], total_count: 1 });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText(/ma_period=120 · pullback_pct=15/)).toBeTruthy());
  });

  it("같은 조합의 뒤 실행은 먼저 돌린 번호를 가리킨다 — 더 오래된 쪽이 원본이다", async () => {
    // 목록은 최신순으로 온다.
    selectRuns.mockResolvedValue({
      items: [aRun(686, { ma_period: 120, pullback_pct: 15 }), aRun(661, { ma_period: 120, pullback_pct: 15 })],
      total_count: 2,
    });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText("#686")).toBeTruthy());
    // 줄은 번호로 시작한다 — `includes("#661")` 로 찾으면 #686 줄의 안내문이 먼저 잡힌다.
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(rows.find((r) => r.startsWith("#686"))).toContain("같은 조합을 #661 에서 이미 돌렸습니다");
    expect(rows.find((r) => r.startsWith("#661"))).not.toContain("이미 돌렸습니다");
  });

  it("조합이 다르면 반복이라 하지 않는다", async () => {
    selectRuns.mockResolvedValue({
      items: [aRun(12, { ma_period: 20 }), aRun(11, { ma_period: 5 })],
      total_count: 2,
    });

    render(<BotRunHistory botId={7} />);

    await waitFor(() => expect(screen.getByText("#12")).toBeTruthy());
    expect(screen.queryByText(/이미 돌렸습니다/)).toBeNull();
  });
});
