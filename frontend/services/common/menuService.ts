import { apiCall } from "@/utils/common/api/client";
import { MenuOut, MenusOut, MenuCreateInSchema, MenuUpdateInSchema, MenuParentOptionOut } from "@/schemas/common/menu";
import { AuthorOptionsOut } from "@/schemas/common/author";
import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/common/system/menu";

export const selectMenuList = async (params: any): Promise<MenusOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<MenusOut>(BASE_URL, { method: "GET", params: queryParams });
};

export const selectMenu = async (data: any): Promise<MenuOut | null> => {
  const { menu_id } = data;
  return apiCall<MenuOut>(`${BASE_URL}/${menu_id}`, { method: "GET" });
};

export const createMenu = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(MenuCreateInSchema, data);
    return apiCall<CreateOut>(BASE_URL, { method: "POST", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const updateMenu = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { menu_id, ...baseData } = data;
    const validatedData = validateWithZod(MenuUpdateInSchema, baseData);
    return apiCall<UpdateOut>(`${BASE_URL}/${menu_id}`, { method: "PUT", data: validatedData });
  } catch (error) {
    handleZodValidationError(error);
  }
};

export const deleteMenu = async (data: any): Promise<DeleteOut | null> => {
  const { menu_id } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${menu_id}`, { method: "DELETE" });
};

export const fetchNavigation = async (): Promise<{ items: any[] }> => {
  const result = await apiCall<{ items: any[] }>(`${BASE_URL}/navigation`, { method: "GET" });
  return result ?? { items: [] };
};

export const selectMenuAuthors = async (menu_id: string) =>
  apiCall<AuthorOptionsOut>(`${BASE_URL}/${menu_id}/author`, { method: "GET" });

export const addMenuAuthor = async (menu_id: string, author_id: string) =>
  apiCall<{ message?: string }>(`${BASE_URL}/${menu_id}/author`, {
    method: "POST",
    data: { author_id },
  });

export const removeMenuAuthor = async (menu_id: string, author_id: string) =>
  apiCall<{ message?: string }>(`${BASE_URL}/${menu_id}/author/${author_id}`, { method: "DELETE" });

export const selectMenuParentOptions = async (): Promise<MenuParentOptionOut[]> => {
  const result = await apiCall<{ data: MenuParentOptionOut[] }>(BASE_URL, {
    method: "GET",
    params: { parent_options: true },
  });
  return result?.data ?? [];
};
