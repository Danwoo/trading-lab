"use client";

import { useMemo } from "react";
import { useIngestRuns } from "@/hooks/terminal/useIngestRuns";
import { describeStaleness, type StalenessNote } from "@/lib/terminal/staleness";
import type { IngestRunOut } from "@/schemas/terminal/ingest";
import type { Provenance } from "@/types/terminal/provenance";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

/** 시세 신선도를 좌우하는 잡 — 종목 마스터는 캔들이 아니라서 「시세가 언제까지 있나」에 답하지 않는다. */
const CANDLE_JOB_KINDS = ["daily_bar", "minute_bar"];

/**
 * 보드가 답해야 하는 질문은 하나다 — **「지금 보는 숫자를 믿어도 되나」**(§21.5).
 * 그래서 갈래를 「좋음/나쁨」이 아니라 **사용자가 해야 할 일이 다른 단위**로 가른다.
 */
export type QuoteFreshnessKind =
  /** 아직 확인 중 — 낡았는지 아닌지 모른다. 모르는 것을 최신으로 그리지 않는다 */
  | "checking"
  /** 오늘 적재본이 있다 */
  | "fresh"
  /** 적재본이 있는데 하루 이상 낡았다 */
  | "stale"
  /** 캔들 적재를 한 번도 돌리지 않았다 */
  | "never-run"
  /** 적재를 돌렸는데 마지막 시도가 실패했고, 성공한 적재본이 하나도 없다 */
  | "never-succeeded"
  /** 적재 이력 자체를 못 읽었다 — 신선도를 판정할 근거가 없다 */
  | "unreadable";

export interface QuoteFreshness {
  kind: QuoteFreshnessKind;
  /** 배지가 그대로 쓰는 출처. `loaded` 의 `asOf` 는 적재본이 덮는 마지막 날이다 */
  provenance: Provenance;
  staleness: StalenessNote | null;
  /** 지금 큐에 있거나 돌고 있는 캔들 적재가 있나 — 「없음」과 「받는 중」은 다르다 */
  running: boolean;
  /** 마지막 시도가 남긴 사유. 화면은 이것을 **영향 범위 뒤에** 놓는다(§21.5) */
  failedReason: string | null;
}

/** 적재본이 덮는 마지막 날 — 기간이 있으면 그것이 답이고, 없으면 실행 시각으로 대신한다. */
function coverageOf(run: IngestRunOut): string | null {
  return run.period_to ?? run.finished_dt ?? run.started_dt ?? run.reg_dt;
}

/**
 * 시세 적재본이 얼마나 낡았나 — 보드 상단의 상시 배지(§21.5)가 읽는 값.
 *
 * 데이터는 새로 만들지 않고 **적재 이력(`useIngestRuns`)을 그대로 재해석**한다. `tn_ingest_run`
 * 하나가 요청·실행·이력을 겸하므로(M2-AD-12) 「어디까지 받았나」의 답이 이미 그 목록 안에 있다.
 *
 * 「지금」은 `Date.now()` 로 읽되 **적재 이력이 도착한 뒤에만** 쓴다. 목록은 클라이언트에서만
 * 채워지므로(`useOnDemand` 가 이펙트에서 요청한다) 서버 렌더에는 `asOf` 가 없고, 그래서 첫
 * 페인트가 서버·클라이언트에서 갈리지 않는다.
 */
export function useQuoteFreshness(): QuoteFreshness {
  const runs = useIngestRuns(0, true);

  return useMemo<QuoteFreshness>(() => {
    // `placeholder` 는 「아직 아무것도 안 물어봤다」(훅의 초기 상태)이거나 「엔드포인트가 아직
    // 없다」다. 어느 쪽이든 **아직 답이 없는 것**이라 확인 중으로 둔다 — 답이 없을 때 최신으로
    // 그리는 것이 §21.5 가 금지한 바로 그것이고, 확인 중은 적어도 아무것도 주장하지 않는다.
    if (runs.isLoading || runs.provenance.kind === "placeholder") {
      return {
        kind: "checking",
        provenance: { kind: "unavailable", reason: "시세 적재 상태를 확인하고 있습니다" },
        staleness: null,
        running: false,
        failedReason: null,
      };
    }

    if (runs.data === null) {
      const reason = runs.provenance.kind === "unavailable" ? runs.provenance.reason : "적재 이력을 읽지 못했습니다";
      return {
        kind: "unreadable",
        provenance: { kind: "unavailable", reason },
        staleness: null,
        running: false,
        failedReason: runs.error ? getApiErrorMessage(runs.error) : null,
      };
    }

    const candleRuns = runs.data.filter((run) => CANDLE_JOB_KINDS.includes(run.job_kind));
    const running = candleRuns.some((run) => run.status === "queued" || run.status === "running");

    if (candleRuns.length === 0) {
      return {
        kind: "never-run",
        provenance: { kind: "unavailable", reason: "캔들 적재를 아직 한 번도 돌리지 않았습니다" },
        staleness: null,
        running: false,
        failedReason: null,
      };
    }

    // 목록은 `run_id DESC` 라 첫 성공분이 곧 가장 최근 성공분이다.
    const succeeded = candleRuns.find((run) => run.status === "succeeded");
    if (!succeeded) {
      const last = candleRuns[0];
      return {
        kind: running ? "never-run" : "never-succeeded",
        provenance: {
          kind: "unavailable",
          reason: running ? "첫 적재가 아직 끝나지 않았습니다" : "성공한 캔들 적재가 없습니다",
        },
        staleness: null,
        running,
        failedReason: last.failed_reason,
      };
    }

    const asOf = coverageOf(succeeded);
    const staleness = describeStaleness(asOf, Date.now());
    return {
      kind: staleness ? "stale" : "fresh",
      provenance: { kind: "loaded", source: "시세", asOf },
      staleness,
      running,
      failedReason: candleRuns[0].status === "failed" ? candleRuns[0].failed_reason : null,
    };
  }, [runs.data, runs.isLoading, runs.error, runs.provenance]);
}
