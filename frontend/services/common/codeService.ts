import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import {
  CodeGroupCreateInSchema,
  CodeGroupUpdateInSchema,
  CodeCreateInSchema,
  CodeUpdateInSchema,
  CodeGroupsOut,
  CodeGroupOut,
  CodeOut,
  CodesOut,
} from "@/schemas/common/code";
import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/common/system/code-group";

// 코드 그룹 목록 조회
export const selectCodeGroupList = async (params: any): Promise<CodeGroupsOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<CodeGroupsOut>(BASE_URL, { method: "GET", params: queryParams });
};

// 단일 코드 그룹 조회
export const selectCodeGroup = async (data: any): Promise<CodeGroupOut | null> => {
  const { group_code } = data;
  return apiCall<CodeGroupOut>(`${BASE_URL}/${group_code}`, { method: "GET" });
};

// 코드 그룹 생성
export const createCodeGroup = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(CodeGroupCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 코드 그룹 수정
export const updateCodeGroup = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { group_code, ...baseData } = data;
    const validatedData = validateWithZod(CodeGroupUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${group_code}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 코드 그룹 삭제
export const deleteCodeGroup = async (data: any): Promise<DeleteOut | null> => {
  const { group_code } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${group_code}`, { method: "DELETE" });
};

// 코드 목록
export const selectCodeList = async (params: any): Promise<CodesOut | null> => {
  const { group_code, ...queryParams } = params;
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<CodesOut>(`${BASE_URL}/${group_code}/code`, { method: "GET", params: queryParams });
};

// 단일 코드 조회
export const selectCode = async (data: any): Promise<CodeOut | null> => {
  const { group_code, code } = data;
  return apiCall<CodeOut>(`${BASE_URL}/${group_code}/code/${code}`, { method: "GET" });
};

// 코드 생성
export const createCode = async (data: any): Promise<CreateOut | null> => {
  try {
    const { group_code, ...baseData } = data;
    const validatedData = validateWithZod(CodeCreateInSchema, baseData);
    return apiCall<CreateOut>(`${BASE_URL}/${group_code}/code`, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 코드 수정
export const updateCode = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { group_code, code, ...baseData } = data;
    const validatedData = validateWithZod(CodeUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${group_code}/code/${code}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 코드 삭제
export const deleteCode = async (data: any): Promise<DeleteOut | null> => {
  const { group_code, code } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${group_code}/code/${code}`, { method: "DELETE" });
};
