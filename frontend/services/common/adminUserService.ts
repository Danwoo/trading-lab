import { apiCall } from "@/utils/common/api/client";
import {
  AdminUserOut,
  AdminUsersOut,
  AdminUserUpdateInSchema,
  AdminUserCreateInSchema,
  UserSessionsOut,
  UserOptionsOut,
} from "@/schemas/common/adminUser";
import { AuthorOptionsOut } from "@/schemas/common/author";
import { UpdateOut, DeleteOut } from "@/schemas/common/types";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/common/system/adminuser";

export const createAdminUser = async (data: any): Promise<{ message: string } | null> => {
  try {
    const validatedData = validateWithZod(AdminUserCreateInSchema, data);
    return apiCall<{ message: string }>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

/** 사용자 선택 피커용 옵션 목록 (워크스페이스 범위 — 운영자는 자기 워크스페이스, 관리자는 전체) */
export const selectUserOptions = async (): Promise<UserOptionsOut | null> =>
  apiCall<UserOptionsOut>(`${BASE_URL}/options`, { method: "GET" });

export const selectAdminUserList = async (params: any): Promise<AdminUsersOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<AdminUsersOut>(BASE_URL, { method: "GET", params: queryParams });
};

export const selectAdminUser = async (data: any): Promise<AdminUserOut | null> => {
  const { email } = data;
  return apiCall<AdminUserOut>(`${BASE_URL}/${encodeURIComponent(email)}`, { method: "GET" });
};

export const updateAdminUser = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { email, ...baseData } = data;
    const validatedData = validateWithZod(AdminUserUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${encodeURIComponent(email)}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deleteAdminUser = async (data: any): Promise<DeleteOut | null> => {
  const { email } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${encodeURIComponent(email)}`, { method: "DELETE" });
};

export const selectUserAuthors = async (email: string) =>
  apiCall<AuthorOptionsOut>(`${BASE_URL}/${encodeURIComponent(email)}/author`, { method: "GET" });

const AUTHOR_BASE_URL = "/api/common/system/author";

export const addUserAuthor = async (email: string, author_id: string) =>
  apiCall<{ message?: string }>(`${AUTHOR_BASE_URL}/${encodeURIComponent(author_id)}/user`, {
    method: "POST",
    data: { user_id: email },
  });

// N3(PR #337 4차 리뷰) — author_id 만 인코딩이 빠져 같은 파일 안에서 규칙이 갈리던 것을 맞춤.
// 이 라우트는 브라우저 → 자체 Next API 호출이라 신뢰경계는 아니지만(차단급 아님), 일관성 차원.
export const removeUserAuthor = async (email: string, author_id: string) =>
  apiCall<{ message?: string }>(
    `${AUTHOR_BASE_URL}/${encodeURIComponent(author_id)}/user/${encodeURIComponent(email)}`,
    {
      method: "DELETE",
    },
  );

export const selectUserSessions = async (email: string) =>
  apiCall<UserSessionsOut>(`${BASE_URL}/${encodeURIComponent(email)}/session`, { method: "GET" });

export const revokeUserSession = async (email: string, id: string): Promise<{ message: string } | null> =>
  apiCall<{ message: string }>(`${BASE_URL}/${encodeURIComponent(email)}/session?id=${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
