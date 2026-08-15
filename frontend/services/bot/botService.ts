import { CreateOut, DeleteOut, UpdateOut } from "@/schemas/common/types";
import {
  BotCreateInSchema,
  BotDetailOut,
  BotUpdateInSchema,
  BotsOut,
  StrategyCatalogOut,
  StrategyField,
  StrategyForm,
} from "@/schemas/bot/bot";
import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/bot"
const BASE_URL = "/api/external/backend/bot";

const stringifyGridParams = (params: any): Record<string, any> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);
  return queryParams;
};

/**
 * 전략 목록 — 봇 만들기 폼의 재료.
 *
 * 전략은 **파일**이라 목록이 코드가 아니라 디스크에서 온다. 그래서 「없음」과 「못 읽음」이
 * 갈리고, 응답의 `errors` 가 후자를 담는다 — 화면은 그것을 이유로 보여준다.
 */
export const selectStrategyCatalog = async (): Promise<StrategyCatalogOut | null> => {
  return apiCall<StrategyCatalogOut>(`${BASE_URL}/strategy-catalog`, { method: "GET" });
};

// 봇 목록 조회
export const selectBotList = async (params: any): Promise<BotsOut | null> => {
  return apiCall<BotsOut>(BASE_URL, { method: "GET", params: stringifyGridParams(params) });
};

// 봇 단건 조회 (실린 전략 포함)
export const selectBot = async (botId: number): Promise<BotDetailOut | null> => {
  return apiCall<BotDetailOut>(`${BASE_URL}/${botId}`, { method: "GET" });
};

// 봇 등록
export const createBot = async (data: any): Promise<CreateOut | null> => {
  try {
    const validated = validateWithZod(BotCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validated });
  } catch (error) {
    handleZodValidationError(error);
    return null;
  }
};

// 봇 수정 — `strategies` 를 안 보내면 실린 전략을 건드리지 않는다
export const updateBot = async (botId: number, data: any): Promise<UpdateOut | null> => {
  try {
    const validated = validateWithZod(BotUpdateInSchema, data);
    return apiCall<UpdateOut>(`${BASE_URL}/${botId}`, { method: "PUT", data: validated });
  } catch (error) {
    handleZodValidationError(error);
    return null;
  }
};

// 봇 삭제
export const deleteBot = async (botId: number): Promise<DeleteOut | null> => {
  return apiCall<DeleteOut>(`${BASE_URL}/${botId}`, { method: "DELETE" });
};

/**
 * 전략 선언의 기본값으로 파라미터를 채운다 — 폼을 열자마자 유효한 상태가 되게 한다.
 *
 * 백엔드도 빠진 값을 기본값으로 채우지만(`validate_param_values`), 화면이 먼저 채워야
 * 사용자가 **무엇이 설정될지 보면서** 고를 수 있다. 실험대 스펙 §8.6.1 의 「대화가 폼을 채우고,
 * 폼이 대화를 검증한다」가 성립하려면 폼이 언제나 지금 값을 보여줘야 한다.
 */
export const defaultParams = (form: StrategyForm): Record<string, unknown> =>
  Object.fromEntries(form.fields.map((field: StrategyField) => [field.name, field.default]));
