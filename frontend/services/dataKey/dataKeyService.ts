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

export interface DataKeyProbe {
  /** 키가 통했는가. */
  ok: boolean;
  /** 실제로 물어봤는가 — 확인 호출이 없는 소스는 `false` 다(「실패」와 다르다). */
  checked: boolean;
  /** 사람이 읽을 사유. **값을 담지 않는다.** */
  detail: string;
}

export interface DataKeySaved {
  source: string;
  setting: string;
  action: string;
  restart_required: boolean;
}

/**
 * 넣으려는 값으로 소스에 한 번 물어본다 — **저장 전에** 확인한다.
 *
 * `setting` 은 값이 둘인 소스(예: 앱 ID + 시크릿)에서 어느 항목인지 지목한다. 서버는 그
 * 소스의 표에 적힌 이름만 받으므로 임의 변수를 가리킬 수 없다.
 */
export const probeDataKey = async (source: string, value: string, setting: string): Promise<DataKeyProbe | null> => {
  return apiCall<DataKeyProbe>(`${BASE_URL}/probe`, { method: "POST", data: { source, value, setting } });
};

/** 키를 그 서비스의 `.env` 에 쓴다 — 로컬 개발에서만 열린다. */
export const saveDataKey = async (source: string, value: string, setting: string): Promise<DataKeySaved | null> => {
  return apiCall<DataKeySaved>(BASE_URL, { method: "PUT", data: { source, value, setting } });
};
