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
import { cleanup, renderHook, waitFor } from "@testing-library/react";

import { useBacktestBoard } from "@/hooks/bench/useBacktestBoard";

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
