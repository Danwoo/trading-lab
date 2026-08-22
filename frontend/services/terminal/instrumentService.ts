import { apiCall } from "@/utils/common/api/client";
import type { InstrumentsOut } from "@/schemas/terminal/instrument";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/instrument"
const INSTRUMENT_URL = "/api/external/backend/instrument";

/**
 * 적재된 종목 마스터(`tn_instrument`)를 이름·코드로 훑는다 (#318).
 *
 * `throwOnFailure: true` 로 부른다 — 서버 실패를 `null` 로 받으면 화면이 그것을 「검색 결과
 * 없음」으로 그리고, 사용자는 멀쩡히 있는 종목을 없다고 읽는다(#332 가 보유 탭에서 같은 자리를
 * 닫았다).
 */
export async function selectInstrumentList(params: {
  q?: string;
  market?: string;
  skip?: number;
  take?: number;
}): Promise<InstrumentsOut | null> {
  return apiCall<InstrumentsOut>(INSTRUMENT_URL, { method: "GET", params, throwOnFailure: true });
}
