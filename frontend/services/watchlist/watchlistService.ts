import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import {
  WatchlistCreateInSchema,
  WatchlistUpdateInSchema,
  WatchlistsOut,
  WatchlistOut,
} from "@/schemas/watchlist/watchlist";
import { apiCall } from "@/utils/common/api/client";
import { uploadFiles, deleteAllFiles } from "@/services/common/fileService";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/watchlist"
const BASE_URL = "/api/external/backend/watchlist";

const stringifyGridParams = (params: any): Record<string, any> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);
  return queryParams;
};

// 관심종목 목록 조회
export const selectWatchlistList = async (params: any): Promise<WatchlistsOut | null> => {
  return apiCall<WatchlistsOut>(BASE_URL, { method: "GET", params: stringifyGridParams(params) });
};

// 관심종목 단건 조회
export const selectWatchlist = async (data: any): Promise<WatchlistOut | null> => {
  return apiCall<WatchlistOut>(`${BASE_URL}/${data.ticker}`, { method: "GET" });
};

// 관심종목 등록
// Zod 검증 → 리서치 문서 업로드(atch_file_id 확보) → API 호출 순서 (옛 todoService 패턴)
export const createWatchlist = async (data: any): Promise<CreateOut | null> => {
  try {
    const { researchFiles, ...validatedData } = validateWithZod(WatchlistCreateInSchema, data);

    if (researchFiles?.length) {
      const uploadResult = await uploadFiles(researchFiles, validatedData.atch_file_id);
      if (uploadResult?.data.atch_file_id) {
        validatedData.atch_file_id = uploadResult.data.atch_file_id;
      }
    }

    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 관심종목 수정
export const updateWatchlist = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { ticker, ...baseData } = data;
    const { researchFiles, ...validatedData } = validateWithZod(WatchlistUpdateInSchema, baseData);

    if (researchFiles?.length) {
      const uploadResult = await uploadFiles(researchFiles, validatedData.atch_file_id);
      if (uploadResult?.data.atch_file_id) {
        validatedData.atch_file_id = uploadResult.data.atch_file_id;
      }
    }

    return apiCall<UpdateOut>(`${BASE_URL}/${ticker}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 관심종목 삭제 — 첨부된 리서치 문서도 함께 삭제 (옛 todoService 패턴)
export const deleteWatchlist = async (data: any): Promise<DeleteOut | null> => {
  const { atch_file_id, ticker } = data;

  if (atch_file_id) {
    try {
      await deleteAllFiles(atch_file_id);
    } catch {
      // 파일 삭제 실패는 무시 (관심종목 삭제는 계속 진행)
    }
  }

  return apiCall<DeleteOut>(`${BASE_URL}/${ticker}`, { method: "DELETE" });
};
