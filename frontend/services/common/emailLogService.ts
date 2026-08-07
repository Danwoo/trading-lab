import { apiCall } from "@/utils/common/api/client";

const BASE_URL = "/api/common/system/email-log";

export const selectEmailLogList = async (params: any) => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<{ items: any[]; total_count: number }>(BASE_URL, { method: "GET", params: queryParams });
};
