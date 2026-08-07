import { NavHistoryOut } from "@/schemas/nav/nav";
import { apiCall } from "@/utils/common/api/client";

const BASE_URL = "/api/external/backend/nav";

/**
 * NAV 시계열 이력 조회 (대시보드 차트/카드/로그용)
 */
export const selectNavHistory = async (minutes: number): Promise<NavHistoryOut | null> => {
  return apiCall<NavHistoryOut>(`${BASE_URL}/history`, {
    method: "GET",
    params: { minutes },
  });
};
