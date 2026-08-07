import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import {
  PortfolioCreateInSchema,
  PortfolioUpdateInSchema,
  PortfoliosOut,
  PortfolioOut,
  HoldingCreateInSchema,
  HoldingUpdateInSchema,
  HoldingsOut,
} from "@/schemas/portfolio/portfolio";
import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/external/backend/portfolio";

const stringifyGridParams = (params: any): Record<string, any> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);
  return queryParams;
};

interface SelectListOptions {
  /** #332 — 서버 실패(`success:false`)와 정상 응답 0건을 구분해야 하는 호출부용. 기본 false. */
  throwOnFailure?: boolean;
}

// ── Portfolio (master) ─────────────────────────────────────────────────
export const selectPortfolioList = async (params: any, options?: SelectListOptions): Promise<PortfoliosOut | null> => {
  return apiCall<PortfoliosOut>(BASE_URL, {
    method: "GET",
    params: stringifyGridParams(params),
    throwOnFailure: options?.throwOnFailure,
  });
};

export const selectPortfolio = async (data: any): Promise<PortfolioOut | null> => {
  return apiCall<PortfolioOut>(`${BASE_URL}/${data.portfolio_id}`, { method: "GET" });
};

export const createPortfolio = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(PortfolioCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const updatePortfolio = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { portfolio_id, ...baseData } = data;
    const validatedData = validateWithZod(PortfolioUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${portfolio_id}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deletePortfolio = async (data: any): Promise<DeleteOut | null> => {
  return apiCall<DeleteOut>(`${BASE_URL}/${data.portfolio_id}`, { method: "DELETE" });
};

// ── Holding (detail) ───────────────────────────────────────────────────
export const selectHoldingList = async (params: any, options?: SelectListOptions): Promise<HoldingsOut | null> => {
  const { portfolio_id, ...rest } = params;
  return apiCall<HoldingsOut>(`${BASE_URL}/${portfolio_id}/holding`, {
    method: "GET",
    params: stringifyGridParams(rest),
    throwOnFailure: options?.throwOnFailure,
  });
};

export const createHolding = async (data: any): Promise<CreateOut | null> => {
  try {
    const { portfolio_id, ...baseData } = data;
    const validatedData = validateWithZod(HoldingCreateInSchema, baseData);
    return apiCall<CreateOut>(`${BASE_URL}/${portfolio_id}/holding`, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const updateHolding = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { portfolio_id, ticker, ...baseData } = data;
    const validatedData = validateWithZod(HoldingUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${portfolio_id}/holding/${ticker}`, {
      method: "PUT",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deleteHolding = async (data: any): Promise<DeleteOut | null> => {
  return apiCall<DeleteOut>(`${BASE_URL}/${data.portfolio_id}/holding/${data.ticker}`, { method: "DELETE" });
};
