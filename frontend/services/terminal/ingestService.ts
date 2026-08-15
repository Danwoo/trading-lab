import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";
import { IngestRunCreateInSchema, type IngestRunsOut } from "@/schemas/terminal/ingest";
import type { CreateOut } from "@/schemas/common/types";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/ingest-run"
const INGEST_RUN_URL = "/api/external/backend/ingest-run";

/**
 * 적재 잡 이력. `tn_ingest_run` 하나가 요청·실행·이력을 겸하므로(M2-AD-12) 목록 조회가 곧
 * FR-010("어디까지 받았고 무엇이 실패했는지")의 답이다 — 별도 상태 API 가 없는 이유다.
 */
export async function selectIngestRunList(params: {
  skip?: number;
  take?: number;
  sort?: string;
}): Promise<IngestRunsOut | null> {
  return apiCall<IngestRunsOut>(INGEST_RUN_URL, { method: "GET", params });
}

/**
 * 수동 적재 요청. 큐에 넣고 즉시 반환하며 실행은 백그라운드 워커가 집어 간다 — 응답의
 * `run_id` 는 "실행됐다"가 아니라 "줄을 섰다"는 뜻이다.
 */
export async function insertIngestRun(data: unknown): Promise<CreateOut | null> {
  try {
    const validated = validateWithZod(IngestRunCreateInSchema, data);
    return apiCall<CreateOut>(INGEST_RUN_URL, { method: "POST", data: validated });
  } catch (error) {
    handleZodValidationError(error);
  }
}
