// services/devActivity/devActivityService.ts
import { apiCall } from "@/utils/common/api/client";
import { fetchSSE, SSEChunk } from "@/utils/common/api/sse";
import { AccountInfo, HolderInfo, ChatRequest } from "@/schemas/devActivity/devActivity";

const BASE_URL = "/api/external/devactivity/chat";

// chat_router.py 의 SSE 이벤트 — type 판별자 없이 status/content/error 필드만으로 분기한다
// (portfolio_chat_service.py 가 {"status": ...} | {"content": ...} 를 yield, [DONE] 은 fetchSSE 가
// JSON.parse 실패로 무시하며 자연 종료).
interface DevActivityChatChunk extends SSEChunk {
  status?: string;
  content?: string;
}

/** 계좌·포트폴리오 목록 (account_id·name·kind·base_ccy) — 좌측 목록 + 계좌 범위 필터용 */
export const selectAccounts = async (): Promise<AccountInfo[]> => {
  const res = await apiCall<{ items: AccountInfo[]; total_count: number }>(`${BASE_URL}/accounts`, { method: "GET" });
  return res?.items ?? [];
};

/** 계좌주 목록 — 계좌주 필터 드롭다운용 */
export const selectHolders = async (): Promise<HolderInfo[]> => {
  const res = await apiCall<{ items: HolderInfo[]; total_count: number }>(`${BASE_URL}/holders`, { method: "GET" });
  return res?.items ?? [];
};

interface StreamChatOptions {
  onStatus?: (text: string) => void; // 진행 단계 (질의 분석 / 포트폴리오 조회 …)
  onDelta: (text: string) => void; // 답변 토큰
  signal?: AbortSignal;
}

/**
 * 질문을 보내고 진행상태(onStatus)·답변 토큰(onDelta)을 SSE 로 받아 흘려보낸다 (멀티턴 — history 동봉).
 * 스트리밍은 apiCall(axios) 로 소비 불가 → sse.ts 의 fetchSSE(룰6 예외 파일) 경유
 * (research-chat 처럼 서비스 파일에서 raw fetch 를 직접 쓰지 않는다).
 */
export const streamChat = async (req: ChatRequest, { onStatus, onDelta, signal }: StreamChatOptions): Promise<void> => {
  await fetchSSE<DevActivityChatChunk>({
    url: BASE_URL,
    body: req,
    signal,
    onChunk: (chunk) => {
      if (chunk.error) throw new Error(chunk.error);
      if (chunk.status) onStatus?.(chunk.status);
      if (chunk.content) onDelta(chunk.content);
    },
  });
};
