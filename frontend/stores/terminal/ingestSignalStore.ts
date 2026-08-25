"use client";

import { create } from "zustand";
import type { IngestRunOut } from "@/schemas/terminal/ingest";

/**
 * 적재가 적재본을 바꿨다는 신호 — 적재 콘솔이 쓰고, 적재본을 읽는 자리가 구독한다.
 *
 * 적재는 DB 를 바꾸지만 이미 조회를 마친 화면은 그것을 알 길이 없다. 그래서 「받음 · 242행」
 * 옆에서 차트가 「아직 적재되지 않았습니다」라고 말했다(#350). 여기가 그 통로다: 잡 하나가
 * **자기가 채운 자리의 키**에 붙은 세대 번호를 올리고, 그 키를 읽는 훅이 세대가 바뀐 것을
 * 보고 다시 받는다.
 *
 * 키로 가르는 이유는 **받은 것과 상관없는 자리를 다시 그리지 않기** 위해서다 — 세대 번호
 * 하나를 전역으로 두면 어느 종목을 받든 열린 패널이 전부 다시 요청한다.
 */

/** 더는 진행되지 않는 상태. `rate_limited` 도 여기다 — 실패가 아니라 **받은 만큼은 들어간** 상태다. */
const TERMINAL_STATUSES: ReadonlySet<string> = new Set(["succeeded", "failed", "rate_limited"]);

function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

/**
 * 적재본 캔들의 신호 키 — 시장:티커.
 *
 * **주기(일봉/분봉)로 더 가르지 않는다.** 분봉 적재가 일봉 응답을 바꾸기 때문이다:
 * `bar_service._fold_regular_session` 이 조회 시점에 분봉으로 일봉을 접어 갈아 끼운다.
 * 주기로 갈랐다면 분봉을 받은 뒤 일봉 차트가 옛 값에 머무는 구멍이 남는다.
 */
export function barSignalKey(market: string, ticker: string): string {
  return `bar:${market.toUpperCase()}:${ticker.toUpperCase()}`;
}

/** 종목 마스터의 신호 키 — 시장을 가리지 않는다. 종목 검색은 전 시장을 한 번에 훑는다. */
export const INSTRUMENT_MASTER_SIGNAL_KEY = "instrument-master";

/** 이 잡이 채운 자리들. 모르는 `job_kind` 는 빈 목록이다 — 짐작해서 남의 자리를 흔들지 않는다. */
function signalKeysFor(run: IngestRunOut): string[] {
  if (run.job_kind === "instrument_master") return [INSTRUMENT_MASTER_SIGNAL_KEY];
  if (run.job_kind !== "daily_bar" && run.job_kind !== "minute_bar") return [];

  // 캔들 잡의 `scope` 는 `"NASDAQ:AAPL,MSFT"` 다 — 시장 하나에 종목이 여럿일 수 있다
  // (`IngestRunCreateIn` docstring 이 정본). 콘솔은 한 종목씩만 넣지만 스케줄러·재실행은
  // 목록을 넣을 수 있어, 첫 종목만 읽으면 나머지가 조용히 안 갱신된다.
  const separator = run.scope?.indexOf(":") ?? -1;
  if (run.scope === null || separator < 0) return [];
  const market = run.scope.slice(0, separator);
  return run.scope
    .slice(separator + 1)
    .split(",")
    .map((ticker) => ticker.trim())
    .filter((ticker) => ticker !== "")
    .map((ticker) => barSignalKey(market, ticker));
}

/** 지난 판에서 본 잡의 모습. 이것과 달라진 것만 신호가 된다. */
interface RunMark {
  status: string;
  writtenRows: number;
}

function markOf(run: IngestRunOut): RunMark {
  return { status: run.status, writtenRows: run.written_rows ?? 0 };
}

/**
 * 이 잡이 그새 적재본을 바꿨나.
 *
 * 끝난 것만 보지 않는다 — 워커는 도는 중에도 `written_rows` 를 올리며 커밋한다
 * (`ingest_service` 의 `status='running'` 갱신). 시장 전체를 받는 긴 잡이라면 끝날 때까지
 * 몇 분을 옛 화면으로 기다리게 된다.
 */
function changedSince(previous: RunMark | undefined, next: RunMark): boolean {
  if (previous === undefined) return isTerminalStatus(next.status) || next.writtenRows > 0;
  if (previous.writtenRows !== next.writtenRows) return true;
  return isTerminalStatus(next.status) && !isTerminalStatus(previous.status);
}

interface IngestSignalState {
  /** 신호 키별 세대 번호. 훅은 이 수가 바뀌는 것만 본다. */
  revisionByKey: Record<string, number>;
  /**
   * 마지막으로 본 이력 판. `null` 이면 아직 기준선이 없다 — 첫 판을 신호로 바꾸면 화면을
   * 열 때마다 이미 끝나 있던 잡이 「방금 끝났다」가 되어 헛 재조회가 된다.
   */
  seenRuns: Record<number, RunMark> | null;
}

export const useIngestSignalStore = create<IngestSignalState>(() => ({
  revisionByKey: {},
  seenRuns: null,
}));

/** 적재 이력 한 판을 신호로 바꾼다 — 이력을 폴링하는 적재 콘솔이 매 판마다 부른다. */
export function observeIngestRuns(runs: IngestRunOut[]): void {
  const previous = useIngestSignalStore.getState().seenRuns;
  const seenRuns: Record<number, RunMark> = {};
  for (const run of runs) seenRuns[run.run_id] = markOf(run);

  if (previous === null) {
    useIngestSignalStore.setState({ seenRuns });
    return;
  }

  const bumped = new Set<string>();
  for (const run of runs) {
    if (!changedSince(previous[run.run_id], markOf(run))) continue;
    for (const key of signalKeysFor(run)) bumped.add(key);
  }
  if (bumped.size === 0) {
    useIngestSignalStore.setState({ seenRuns });
    return;
  }

  useIngestSignalStore.setState((state) => {
    const revisionByKey = { ...state.revisionByKey };
    for (const key of bumped) revisionByKey[key] = (revisionByKey[key] ?? 0) + 1;
    return { revisionByKey, seenRuns };
  });
}

/**
 * 이 키의 세대 번호. 훅의 의존성 배열(또는 `useOnDemand` 의 세대 키)에 섞으면 그것이 곧
 * 「적재가 끝나면 다시 받는다」가 된다. `key` 가 `null` 이면(종목 미선택 등) 늘 0 이다.
 */
export function useIngestRevision(key: string | null): number {
  return useIngestSignalStore((state) => (key === null ? 0 : (state.revisionByKey[key] ?? 0)));
}
