import { apiCall } from "@/utils/common/api/client";
import {
  AuthorOut,
  AuthorsOut,
  AuthorOptionsOut,
  AuthorCreateInSchema,
  AuthorUpdateInSchema,
  AuthorUsersOut,
  AuthorMenusOut,
} from "@/schemas/common/author";
import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/common/system/author";

export const selectAuthorList = async (params: any): Promise<AuthorsOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<AuthorsOut>(BASE_URL, { method: "GET", params: queryParams });
};

export const selectAuthor = async (data: any): Promise<AuthorOut | null> => {
  const { author_id } = data;
  return apiCall<AuthorOut>(`${BASE_URL}/${author_id}`, { method: "GET" });
};

export const createAuthor = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(AuthorCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const updateAuthor = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { author_id, ...baseData } = data;
    const validatedData = validateWithZod(AuthorUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${author_id}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deleteAuthor = async (data: any): Promise<DeleteOut | null> => {
  const { author_id } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${author_id}`, { method: "DELETE" });
};

export const selectAuthorOptions = async (): Promise<AuthorOptionsOut | null> =>
  apiCall<AuthorOptionsOut>(`${BASE_URL}/options`, { method: "GET" });

// ==================== 권한 사용자/메뉴 관리 ====================

export const selectAuthorUsers = async (author_id: string): Promise<AuthorUsersOut | null> =>
  apiCall<AuthorUsersOut>(`${BASE_URL}/${author_id}/user`, { method: "GET" });

export const selectAuthorMenus = async (author_id: string): Promise<AuthorMenusOut | null> =>
  apiCall<AuthorMenusOut>(`${BASE_URL}/${author_id}/menu`, { method: "GET" });

export const addAuthorUser = async (author_id: string, user_id: string): Promise<CreateOut | null> =>
  apiCall<CreateOut>(`${BASE_URL}/${author_id}/user`, { method: "POST", data: { user_id } });

export const removeAuthorUser = async (author_id: string, user_id: string): Promise<DeleteOut | null> =>
  apiCall<DeleteOut>(`${BASE_URL}/${author_id}/user/${user_id}`, { method: "DELETE" });

export const addAuthorMenu = async (author_id: string, menu_id: string): Promise<CreateOut | null> =>
  apiCall<CreateOut>(`${BASE_URL}/${author_id}/menu`, { method: "POST", data: { menu_id } });

export const removeAuthorMenu = async (author_id: string, menu_id: string): Promise<DeleteOut | null> =>
  apiCall<DeleteOut>(`${BASE_URL}/${author_id}/menu/${menu_id}`, { method: "DELETE" });
