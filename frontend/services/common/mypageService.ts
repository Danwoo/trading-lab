import { apiCall } from "@/utils/common/api/client";
import { UserInfo, UpdateUserIn, MyInfoOut, UpdateMyInfoOut } from "@/schemas/common/mypage";

const BASE_URL = "/api/common/mypage";

export const fetchMyInfo = async (): Promise<UserInfo | null> => {
  const result = await apiCall<MyInfoOut>(BASE_URL, { method: "GET" });
  if (!result?.result || !result.resultList?.length) return null;
  return result.resultList[0];
};

export const updateMyInfo = async (data: UpdateUserIn): Promise<UpdateMyInfoOut | null> => {
  return apiCall<UpdateMyInfoOut>(BASE_URL, { method: "PATCH", data });
};

export const deleteMyAccount = async (): Promise<{ message: string } | null> => {
  return apiCall<{ message: string }>(BASE_URL, { method: "DELETE" });
};
