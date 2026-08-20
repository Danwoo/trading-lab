// @vitest-environment jsdom
//
// #232 — **봇 이력의 「#11」을 누르면 그 실행의 리포트가 열린다.**
//
// 첫 판은 `/bench?run=<id>` 로 링크만 걸고 그 주소를 읽는 코드를 안 붙였다. 링크는
// 눌리는데 도착지는 빈 실험대라, 「봇을 저장하고 다음에 뭘 하는지 모르겠다」가
// 이력→리포트 구간에서 그대로 남았다. 독립 리뷰가 잡았다.
//
// **검증 경계** — 리포트 조회 서비스를 세운다. 화면에 곡선이 그려지는지는 보지 않는다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";

import { useBacktestBoard } from "@/hooks/bench/useBacktestBoard";
import { GRID_RUN_FAILED_HEADLINE, curveZoneProvenance, gridZoneProvenance } from "@/lib/bench/boardProvenance";
import { runBacktestGrid } from "@/services/backtest/backtestService";

const selectReport = vi.fn();

vi.mock("@/services/backtest/backtestService", () => ({
  runBacktestGrid: vi.fn(),
  selectBacktestReport: (...args: unknown[]) => selectReport(...args),
}));

function givenUrl(search: string) {
  window.history.replaceState({}, "", `/bench${search}`);
}

afterEach(() => {
  cleanup();
  selectReport.mockReset();
  givenUrl("");
});

const AN_EMPTY_REPORT = { run: { run_id: 11 }, equity: [], trades: [], metrics: [] };

describe("#232 `/bench?run=<id>` 로 오면 그 리포트가 열린다", () => {
  it("주소의 실행을 조회한다", async () => {
    selectReport.mockResolvedValue(AN_EMPTY_REPORT);
    givenUrl("?run=11");

    const { result } = renderHook(() => useBacktestBoard());

    await waitFor(() => expect(selectReport).toHaveBeenCalledWith(11));
    await waitFor(() => expect(result.current.report).not.toBeNull());
  });

  it("실행 없이 오면 아무것도 열지 않는다", async () => {
    givenUrl("");

    renderHook(() => useBacktestBoard());

    await waitFor(() => expect(selectReport).not.toHaveBeenCalled());
  });

  it("숫자가 아닌 값은 무시한다", async () => {
    givenUrl("?run=../../etc/passwd");

    renderHook(() => useBacktestBoard());

    await waitFor(() => expect(selectReport).not.toHaveBeenCalled());
  });

  it("못 읽으면 사유가 남는다 — 빈 화면으로 뭉개지 않는다", async () => {
    selectReport.mockRejectedValue(new Error("리포트를 불러오지 못했습니다"));
    givenUrl("?run=11");

    const { result } = renderHook(() => useBacktestBoard());

    await waitFor(() => expect(result.current.reportError).toBe("리포트를 불러오지 못했습니다"));
  });
});

// #284 — 화면은 실패를 두 줄로 낸다: 자리 머리(`GRID_RUN_FAILED_HEADLINE`)와 그 아래 서버 사유
// (`ImpactNotice` 의 `detail`). 훅이 사유로 머리와 같은 문장을 내면 한 화면에 두 번 선다.
// 백엔드가 `{success: false}` 로 200 을 주면 `apiCall` 이 null 을 돌려주는 경로가 정확히 그 자리였다.
describe("격자 실행이 사유 없이 실패한 경로", () => {
  it("자리 머리의 문장을 사유가 되풀이하지 않는다", async () => {
    vi.mocked(runBacktestGrid).mockResolvedValue(null as never);

    const { result } = renderHook(() => useBacktestBoard());
    await act(async () => {
      await result.current.runGrid({} as never);
    });

    const head = gridZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      isRunning: false,
      runError: result.current.runError,
    });
    expect(head.kind === "unavailable" && head.reason).toBe(GRID_RUN_FAILED_HEADLINE);
    expect(result.current.runError).not.toBeNull();
    expect(result.current.runError).not.toContain(GRID_RUN_FAILED_HEADLINE);
  });
});

// 칸 조회가 실패해 사유가 남은 뒤 격자를 다시 돌리면, 곡선 자리가 낡은 「리포트를 불러오지
// 못했습니다」를 계속 말하고 **방금 실행의 실패는 어디에도 안 나온다** — 곡선 판정이
// `reportError` 를 `runError` 보다 먼저 보기 때문이다.
describe("앞선 리포트 실패가 남은 채 격자를 다시 돌리면", () => {
  it("낡은 리포트 실패가 방금 실행의 실패를 가리지 않는다", async () => {
    selectReport.mockRejectedValue(new Error("리포트를 불러오지 못했습니다"));
    vi.mocked(runBacktestGrid).mockResolvedValue(null as never);

    const { result } = renderHook(() => useBacktestBoard());
    act(() => {
      result.current.selectCell(11, "실행 #11");
    });
    await waitFor(() => expect(result.current.reportError).toBe("리포트를 불러오지 못했습니다"));

    await act(async () => {
      await result.current.runGrid({} as never);
    });

    const curve = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      isRunning: false,
      runError: result.current.runError,
      report: null,
      isReportLoading: result.current.isReportLoading,
      reportError: result.current.reportError,
    });
    expect(curve.kind === "unavailable" && curve.because).toBe("run-failed");
  });
});
