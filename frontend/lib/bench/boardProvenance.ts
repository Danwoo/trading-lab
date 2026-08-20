import type { Provenance, UnavailableBecause } from "@/types/terminal/provenance";

/**
 * 격자 실행이 실패했을 때 **화면에 실제로 나가는 머리 문장**. 자리의 사유이자 알림(`ImpactNotice`)의
 * 머리줄이라 한 자리에 둔다 — 두 벌로 두면 한쪽만 고쳐져 배지와 알림이 다른 말을 한다.
 *
 * 서버 사유는 여기 붙이지 않는다. 원인은 알림의 `detail` 이 맨 뒤에 낸다(화면 결정 §21.5).
 */
export const GRID_RUN_FAILED_HEADLINE = "격자 실행이 실패했습니다";

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
  /** 실행이 지금 돌고 있나 — 「아직 안 돌렸다」와 갈라야 하는 상태다 */
  isRunning: boolean;
  /** 마지막 실행이 실패했을 때의 서버 사유 */
  runError: string | null;
}

/**
 * 격자 자리의 출처 (#284 · #291).
 *
 * **실패가 가장 세다.** 실행이 실패했는데 「아직 돌리지 않았습니다」라고 말하면 이미 한 일을
 * 다시 하라고 안내하는 것이고(#291), 앞선 격자가 남아 있을 때 그것만 보여 주면 방금 실패가
 * 화면에서 사라진다. 그래서 실패는 격자 유무보다 먼저 답한다.
 *
 * 「돌고 있다」는 격자가 아직 없을 때만 머리가 말한다 — 앞선 격자가 깔린 채 재실행 중이면
 * 그 칸들은 여전히 참이라 자리는 적재본으로 남는다.
 *
 * 실패의 사유는 `GRID_RUN_FAILED_HEADLINE` 그대로다 — 부르는 쪽이 그것을 알림 머리로 내고
 * 서버 사유는 알림 맨 뒤(`detail`)에 붙인다.
 */
export function gridZoneProvenance({ rosterState, hasGrid, isRunning, runError }: GridZoneInput): Provenance {
  if (runError !== null) {
    return { kind: "unavailable", reason: GRID_RUN_FAILED_HEADLINE, because: "run-failed" };
  }
  if (hasGrid) {
    return { kind: "loaded", source: "백테스트 격자", asOf: null };
  }
  if (isRunning) {
    return {
      kind: "unavailable",
      reason: "격자를 돌리고 있습니다 — 끝나면 조합이 칸으로 깔립니다",
      because: "checking",
    };
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
 * 격자와 같은 순서로 답한다 — 실행이 실패했으면 실패부터 말한다. 다만 **앞선 격자가 남아
 * 있으면 「고를 칸이 없다」는 거짓**이다. 그 칸들은 그대로 눌러 곡선을 채울 수 있으므로,
 * 같은 `run-failed` 안에서 문장을 갈라 준다.
 */
export function curveZoneProvenance({
  rosterState,
  hasGrid,
  isRunning,
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
    return {
      kind: "unavailable",
      reason: hasGrid
        ? "격자 실행이 실패했습니다 — 앞선 격자의 칸은 그대로 고를 수 있습니다"
        : "격자 실행이 실패해 고를 칸이 없습니다",
      because: "run-failed",
    };
  }
  if (hasGrid) {
    return {
      kind: "unavailable",
      reason: "격자에서 칸을 누르면 그 조합의 곡선·지표·거래가 여기 그려집니다",
      because: "not-chosen",
    };
  }
  if (isRunning) {
    return {
      kind: "unavailable",
      reason: "격자를 돌리고 있습니다 — 끝나면 칸을 고를 수 있습니다",
      because: "checking",
    };
  }
  return { kind: "unavailable", reason: CURVE_EMPTY_REASON[rosterState], because: ROSTER_BECAUSE[rosterState] };
}

/**
 * 「내 봇」 자리의 출처 (#284).
 *
 * 「봇이 0개다」는 **읽고 나서야** 할 수 있는 말이라 로스터 상태가 그대로 빔의 종류가 된다.
 * `filled`·`unreadable` 은 훅이 만든 출처(`useBotRoster`)를 그대로 쓴다 — 못 읽은 사유는
 * 훅이 알고, 이 함수는 「아직 안 왔다」·「0건이다」만 갈라 준다.
 */
export function rosterZoneProvenance(rosterState: RosterState, fromRoster: Provenance): Provenance {
  if (rosterState === "loading") {
    return { kind: "unavailable", reason: ROSTER_UNKNOWN.loading, because: "checking" };
  }
  if (rosterState === "empty") {
    return { kind: "unavailable", reason: "아직 만든 봇이 없습니다", because: "empty" };
  }
  return fromRoster;
}
