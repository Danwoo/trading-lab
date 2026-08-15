"use client";

import { useOnDemand } from "@/hooks/terminal/useOnDemand";
import { selectIngestRunList } from "@/services/terminal/ingestService";
import type { IngestRunOut } from "@/schemas/terminal/ingest";
import type { PanelData } from "@/types/terminal/provenance";

/** 한 화면에 담는 이력 수. 목록이 아니라 "최근에 무엇이 돌았나"를 보는 자리다. */
const RUN_PAGE_SIZE = 30;

/**
 * 적재 이력 — 요청형 갈래(③). 백엔드가 `run_id DESC` 로 주므로 최신이 위다.
 *
 * `reloadToken` 이 바뀌면 다시 조회한다 — 잡을 새로 넣은 직후와 주기 갱신에서 쓴다. 폴링을 이
 * 훅 안에 두지 않는 이유는 "언제 다시 볼지"가 화면의 판단이기 때문이다(패널이 접히면 멈춘다).
 */
export function useIngestRuns(reloadToken: number, enabled: boolean): PanelData<IngestRunOut[]> {
  return useOnDemand<IngestRunOut[]>({
    group: `ingest-run:${reloadToken}`,
    enabled,
    source: "적재 이력",
    fetcher: async () => {
      const result = await selectIngestRunList({ skip: 0, take: RUN_PAGE_SIZE });
      const items = result?.items ?? [];
      // 기준 시각은 가장 최근 기록의 시각이다. 목록이 비면 기준 시각이 없다 — 지어내지 않는다.
      const asOf = items[0]?.finished_dt ?? items[0]?.started_dt ?? items[0]?.reg_dt ?? null;
      return { items, asOf };
    },
  });
}
