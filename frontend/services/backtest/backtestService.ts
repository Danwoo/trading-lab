import { BacktestGridInSchema, GridOut, RunReportOut } from "@/schemas/backtest/backtest";
import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/backtest-run"
const BASE_URL = "/api/external/backend/backtest-run";

/** 격자 실행 — 실행이 곧 격자 실행이다 (스펙 D-Q1). 단일 점을 만들지 않는다. */
export const runBacktestGrid = async (data: unknown): Promise<GridOut | null> => {
  try {
    const validated = validateWithZod(BacktestGridInSchema, data);
    return apiCall<GridOut>(`${BASE_URL}/grid`, { method: "POST", data: validated });
  } catch (error) {
    handleZodValidationError(error);
    return null;
  }
};

/** 한 조합의 리포트 — 곡선·거래·지표가 한 번에 온다. 칸 클릭은 계산이 아니라 이 조회다. */
export const selectBacktestReport = async (runId: number): Promise<RunReportOut | null> => {
  return apiCall<RunReportOut>(`${BASE_URL}/${runId}`, { method: "GET" });
};
