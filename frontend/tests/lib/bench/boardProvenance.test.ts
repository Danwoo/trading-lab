// #284 · #291 — **보드의 빈 자리가 자기 상태를 정확히 말한다.**
//
// #291 실측: 격자 실행이 500 으로 실패했는데 자리 머리는 「아직 돌리지 않았습니다 — 봇·종목·
// 구간을 골라 실행하면…」이었다. 이미 한 일을 다시 하라고 안내한 것이다.
// #284 실측: 그 자리 배지는 「⊖ 제공 안 됨」이었는데 바로 아래에 동작하는 실행 폼이 있었다.
//
// 판정은 순수 함수라 여기서 전수로 잡는다 — 페이지 렌더 없이 「어느 상태가 무엇이라 말하나」만 본다.

import { describe, expect, it } from "vitest";

import { curveZoneProvenance, gridZoneProvenance, type RosterState } from "@/lib/bench/boardProvenance";

const ROSTER_STATES: RosterState[] = ["loading", "unreadable", "empty", "filled"];

const IDLE = { isRunning: false };
const NO_CURVE = { report: null, isReportLoading: false, reportError: null };

describe("격자 자리", () => {
  it("봇이 있고 아직 안 돌렸으면 「아직 실행 안 함」이다 — 「제공 안 됨」이 아니다", () => {
    const provenance = gridZoneProvenance({ rosterState: "filled", hasGrid: false, ...IDLE, runError: null });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "아직 돌리지 않았습니다 — 봇·종목·구간을 골라 실행하면 조합이 칸으로 깔립니다",
      because: "not-run",
    });
  });

  it("실행이 실패하면 「아직 돌리지 않았다」고 말하지 않는다 (#291)", () => {
    const provenance = gridZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      ...IDLE,
      runError: "캔들이 없습니다 — 적재를 먼저 돌리세요",
    });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "격자 실행이 실패했습니다 — 캔들이 없습니다 — 적재를 먼저 돌리세요",
      because: "run-failed",
    });
    expect(JSON.stringify(provenance)).not.toContain("아직 돌리지 않았습니다");
  });

  it("앞선 격자가 남아 있어도 방금 실패를 덮지 않는다", () => {
    const provenance = gridZoneProvenance({
      rosterState: "filled",
      hasGrid: true,
      ...IDLE,
      runError: "서버에서 오류",
    });

    expect(provenance.kind).toBe("unavailable");
  });

  it("격자가 있고 실패도 없으면 적재본이다", () => {
    expect(gridZoneProvenance({ rosterState: "filled", hasGrid: true, ...IDLE, runError: null })).toEqual({
      kind: "loaded",
      source: "백테스트 격자",
      asOf: null,
    });
  });

  it("돌고 있는 동안 「골라 실행하면…」이라 말하지 않는다 — 이미 눌렀다", () => {
    const provenance = gridZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      isRunning: true,
      runError: null,
    });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "격자를 돌리고 있습니다 — 끝나면 조합이 칸으로 깔립니다",
      because: "checking",
    });
  });

  it("앞선 격자가 깔린 채 재실행 중이면 그 칸들은 여전히 적재본이다", () => {
    expect(gridZoneProvenance({ rosterState: "filled", hasGrid: true, isRunning: true, runError: null })).toEqual({
      kind: "loaded",
      source: "백테스트 격자",
      asOf: null,
    });
  });

  it("봇 목록의 네 상태가 서로 다른 사유·배지를 갖는다 — 「못 읽음」을 「없음」과 가른다", () => {
    const seen = ROSTER_STATES.map((rosterState) =>
      gridZoneProvenance({ rosterState, hasGrid: false, ...IDLE, runError: null }),
    );
    const becauses = seen.map((p) => (p.kind === "unavailable" ? p.because : "loaded"));

    expect(becauses).toEqual(["checking", "unreadable", "empty", "not-run"]);
    expect(new Set(seen.map((p) => (p.kind === "unavailable" ? p.reason : ""))).size).toBe(ROSTER_STATES.length);
  });
});

describe("곡선 자리", () => {
  it("실행이 실패하면 「격자를 실행하면 곡선이 그려집니다」라고 말하지 않는다 (#291)", () => {
    const provenance = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      ...IDLE,
      runError: "서버에서 오류가 발생했습니다.",
      ...NO_CURVE,
    });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "격자 실행이 실패해 고를 칸이 없습니다",
      because: "run-failed",
    });
  });

  // 앞선 격자가 남은 채 재실행이 실패하면 칸은 화면에 그대로 깔려 있고(`ParamGrid` 는
  // `grid !== null` 에만 걸린다) 눌러서 곡선을 채울 수 있다 — 그때 「고를 칸이 없습니다」는
  // 거짓이다. 배지는 실패로 두되 문장을 갈라야 한다.
  it("앞선 격자가 남아 있으면 「고를 칸이 없다」고 말하지 않는다", () => {
    const provenance = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: true,
      ...IDLE,
      runError: "서버에서 오류가 발생했습니다.",
      ...NO_CURVE,
    });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "격자 실행이 실패했습니다 — 앞선 격자의 칸은 그대로 고를 수 있습니다",
      because: "run-failed",
    });
    expect(JSON.stringify(provenance)).not.toContain("고를 칸이 없습니다");
  });

  it("격자가 있는데 칸을 안 골랐으면 「고르면 채워집니다」다", () => {
    const provenance = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: true,
      ...IDLE,
      runError: null,
      ...NO_CURVE,
    });

    expect(provenance.kind === "unavailable" && provenance.because).toBe("not-chosen");
  });

  it("첫 격자를 돌리는 동안은 「확인 중」이다 — 「아직 안 돌렸다」가 아니다", () => {
    const provenance = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: false,
      isRunning: true,
      runError: null,
      ...NO_CURVE,
    });

    expect(provenance).toEqual({
      kind: "unavailable",
      reason: "격자를 돌리고 있습니다 — 끝나면 칸을 고를 수 있습니다",
      because: "checking",
    });
  });

  it("리포트를 불러오는 중은 「확인 중」이고, 못 읽은 것은 「못 읽음」이다", () => {
    const loading = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: true,
      ...IDLE,
      runError: null,
      report: null,
      isReportLoading: true,
      reportError: null,
    });
    const failed = curveZoneProvenance({
      rosterState: "filled",
      hasGrid: true,
      ...IDLE,
      runError: null,
      report: null,
      isReportLoading: false,
      reportError: "리포트를 불러오지 못했습니다",
    });

    expect(loading.kind === "unavailable" && loading.because).toBe("checking");
    expect(failed.kind === "unavailable" && failed.because).toBe("unreadable");
  });

  it("고른 칸의 리포트가 오면 그 실행이 출처다", () => {
    expect(
      curveZoneProvenance({
        rosterState: "filled",
        hasGrid: true,
        ...IDLE,
        runError: null,
        report: { runId: 42, finishedDt: "2026-08-19T18:00:00" },
        isReportLoading: false,
        reportError: null,
      }),
    ).toEqual({ kind: "loaded", source: "실행 #42", asOf: "2026-08-19T18:00:00" });
  });
});
