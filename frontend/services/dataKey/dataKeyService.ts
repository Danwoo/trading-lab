import { apiCall } from "@/utils/common/api/client";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/data-key"
const BASE_URL = "/api/external/backend/data-key";

/** 키 하나의 상태 — **값은 오지 않는다.** `filled` 는 불리언이다. */
export interface DataKeyStatus {
  source: string;
  setting: string;
  filled: boolean;
  secret: boolean;
  guidance: string | null;
}

interface DataKeyStatusListOut {
  items: DataKeyStatus[];
  total_count: number;
}

/** 어디에 무엇을 넣어야 하는지 — 지금은 문서를 뒤져야 알 수 있다 (#225). */
export const selectDataKeyStatus = async (): Promise<DataKeyStatusListOut | null> => {
  return apiCall<DataKeyStatusListOut>(BASE_URL, { method: "GET" });
};
