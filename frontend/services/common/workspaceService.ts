import { apiCall } from "@/utils/common/api/client";
import {
  WorkspaceOut,
  WorkspacesOut,
  WorkspaceOptionsOut,
  WorkspaceCreateInSchema,
  WorkspaceUpdateInSchema,
  WorkspaceDomainsOut,
  WorkspaceDomainCreateInSchema,
  WorkspaceMenusOut,
  WorkspaceUsersOut,
} from "@/schemas/common/workspace";
import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/common/system/workspace";

// ==================== 워크스페이스 ====================

export const selectWorkspaceList = async (params: any): Promise<WorkspacesOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<WorkspacesOut>(BASE_URL, { method: "GET", params: queryParams });
};

export const selectWorkspace = async (data: any): Promise<WorkspaceOut | null> => {
  const { id } = data;
  return apiCall<WorkspaceOut>(`${BASE_URL}/${id}`, { method: "GET" });
};

export const createWorkspace = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(WorkspaceCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const updateWorkspace = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { id, ...baseData } = data;
    const validatedData = validateWithZod(WorkspaceUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${id}`, {
      method: "PUT",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const selectWorkspaceOptions = async (): Promise<WorkspaceOptionsOut | null> =>
  apiCall<WorkspaceOptionsOut>(`${BASE_URL}/options`, { method: "GET" });

// ==================== 워크스페이스 도메인 ====================

export const selectWorkspaceDomainList = async (params: any): Promise<WorkspaceDomainsOut | null> => {
  const { workspace_id, ...rest } = params;
  const queryParams: Record<string, any> = { ...rest };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<WorkspaceDomainsOut>(`${BASE_URL}/${workspace_id}/domain`, {
    method: "GET",
    params: queryParams,
  });
};

export const createWorkspaceDomain = async (data: any): Promise<CreateOut | null> => {
  try {
    const { workspace_id, ...baseData } = data;
    const validatedData = validateWithZod(WorkspaceDomainCreateInSchema, baseData);
    return apiCall<CreateOut>(`${BASE_URL}/${workspace_id}/domain`, {
      method: "POST",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deleteWorkspaceDomain = async (data: any): Promise<DeleteOut | null> => {
  const { workspace_id, domain } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${workspace_id}/domain/${encodeURIComponent(domain)}`, {
    method: "DELETE",
  });
};

// ==================== 워크스페이스 메뉴 ====================

export const selectWorkspaceMenus = async (workspace_id: number): Promise<WorkspaceMenusOut | null> =>
  apiCall<WorkspaceMenusOut>(`${BASE_URL}/${workspace_id}/menu`, { method: "GET" });

export const addWorkspaceMenu = async (workspace_id: number, menu_id: string): Promise<CreateOut | null> =>
  apiCall<CreateOut>(`${BASE_URL}/${workspace_id}/menu`, {
    method: "POST",
    data: { menu_id },
  });

export const removeWorkspaceMenu = async (workspace_id: number, menu_id: string): Promise<DeleteOut | null> =>
  apiCall<DeleteOut>(`${BASE_URL}/${workspace_id}/menu/${menu_id}`, { method: "DELETE" });

// ==================== 워크스페이스 사용자 (read-only) ====================

export const selectWorkspaceUsers = async (params: any): Promise<WorkspaceUsersOut | null> => {
  const { workspace_id, ...rest } = params;
  const queryParams: Record<string, any> = { ...rest };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<WorkspaceUsersOut>(`${BASE_URL}/${workspace_id}/user`, {
    method: "GET",
    params: queryParams,
  });
};
