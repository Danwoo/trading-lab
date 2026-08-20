import type { Provenance, UnavailableBecause } from "@/types/terminal/provenance";

/** 봇 목록이 지금 어떤 상태인가 — 「못 읽음」·「불러오는 중」을 「없음」과 가른다. */
export type RosterState = "loading" | "unreadable" | "empty" | "filled";

/** 봇 수를 아직 모를 때 두 자리가 공통으로 하는 말. */
export const ROSTER_UNKNOWN: Record<"loading" | "unreadable", string> = {
  loading: "봇 목록을 확인하고 있습니다",
  unreadable: "봇 목록을 읽지 못했습니다 — 봇이 있는지 아직 모릅니다",
};

const GRID_EMPTY_REASON: Record<RosterState, string> = {
  ...ROSTER_UNKNOWN,
  empty: "돌릴 봇이 없습니다 — 봇을 하나 만들면 조합이 여기 깔립니다",
  filled: "아직 돌리지 않았습니다 — 봇·종목·구간을 골라 실행하면 조합이 칸으로 깔립니다",
};

const CURVE_EMPTY_REASON: Record<RosterState, string> = {
  ...ROSTER_UNKNOWN,
  empty: "돌릴 봇이 없습니다 — 봇을 하나 만들면 격자를 실행할 수 있습니다",
  filled: "아직 돌리지 않았습니다 — 격자를 실행하면 곡선이 그려집니다",
};

/** 봇 목록의 상태가 곧 그 자리가 빈 종류다 — 문구가 아니라 이 표로 배지를 정한다. */
const ROSTER_BECAUSE: Record<RosterState, UnavailableBecause> = {
  loading: "checking",
  unreadable: "unreadable",
  empty: "empty",
  filled: "not-run",
};

export interface GridZoneInput {
  rosterState: RosterState;
  /** 격자가 이미 그려져 있나 (`useBacktestBoard` 의 `grid`) */
  hasGrid: boolean;
  /** 마지막 실행이 실패했을 때의 서버 사유 */
  runError: string | null;
}

/**
 * 격자 자리의 출처 (#284 · #291).
 *
 * **실패가 가장 세다.** 실행이 실패했는데 「아직 돌리지 않았습니다」라고 말하면 이미 한 일을
 * 다시 하라고 안내하는 것이고(#291), 앞선 격자가 남아 있을 때 그것만 보여 주면 방금 실패가
 * 화면에서 사라진다. 그래서 실패는 격자 유무보다 먼저 답한다.
 */
export function gridZoneProvenance({ rosterState, hasGrid, runError }: GridZoneInput): Provenance {
  if (runError !== null) {
    return { kind: "unavailable", reason: `격자 실행이 실패했습니다 — ${runError}`, because: "run-failed" };
  }
  if (hasGrid) {
    return { kind: "loaded", source: "백테스트 격자", asOf: null };
  }
  return { kind: "unavailable", reason: GRID_EMPTY_REASON[rosterState], because: ROSTER_BECAUSE[rosterState] };
}

export interface CurveZoneInput extends GridZoneInput {
  /** 고른 칸의 리포트 — 있으면 이 자리가 찬다 */
  report: { runId: number; finishedDt: string | null } | null;
  isReportLoading: boolean;
  reportError: string | null;
}

/**
 * 곡선 자리의 출처 (#284 · #291).
 *
 * 격자와 같은 순서로 답한다 — 실행이 실패했으면 고를 칸 자체가 없으므로 「칸을 누르세요」가
 * 아니라 실패를 말한다.
 */
export function curveZoneProvenance({
  rosterState,
  hasGrid,
  runError,
  report,
  isReportLoading,
  reportError,
}: CurveZoneInput): Provenance {
  if (report !== null) {
    return { kind: "loaded", source: `실행 #${report.runId}`, asOf: report.finishedDt };
  }
  if (isReportLoading) {
    return { kind: "unavailable", reason: "리포트를 불러오고 있습니다", because: "checking" };
  }
  if (reportError !== null) {
    return { kind: "unavailable", reason: reportError, because: "unreadable" };
  }
  if (runError !== null) {
    return { kind: "unavailable", reason: "격자 실행이 실패해 고를 칸이 없습니다", because: "run-failed" };
  }
  if (hasGrid) {
    return {
      kind: "unavailable",
      reason: "격자에서 칸을 누르면 그 조합의 곡선·지표·거래가 여기 그려집니다",
      because: "not-chosen",
    };
  }
  return { kind: "unavailable", reason: CURVE_EMPTY_REASON[rosterState], because: ROSTER_BECAUSE[rosterState] };
}
