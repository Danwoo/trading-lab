// services/researchChat/researchChatService.ts
// #160 슬라이스 D-나: 투자리서치 챗 스트리밍 서비스.
// 스트림은 apiCall(axios) 로 소비 불가 → sse.ts 의 fetchNDJSON(룰6 예외 파일) 경유.
// 서비스 파일에서 raw fetch 를 직접 쓰지 않는다(룰6 클린).
import { fetchNDJSON } from "@/utils/common/api/sse";
import { ResearchChatEvent, ResearchChatRequest, ResearchSource } from "@/schemas/researchChat/researchChat";

const BASE_URL = "/api/external/multi-agent/agent/example-ai";

/** 스트리밍 이벤트별 콜백. onDelta 만 필수, 나머지는 옵션. */
export interface StreamHandlers {
  onStatus?: (text: string) => void; // start/step/routing/tool_parameters → 진행 상태문구
  onDelta: (text: string) => void; // response_chunk → 답변 토큰(누적)
  onSources?: (sources: ResearchSource[]) => void; // media → 근거 카드
  onTitle?: (title: string) => void; // title → 세션 자동 제목
  onFollowUps?: (questions: string[]) => void; // follow_up_question → 후속질문
  signal?: AbortSignal;
}

/**
 * 질문을 /agent/example-ai 로 보내고 NDJSON 이벤트를 type 별 콜백으로 흘려보낸다.
 * gid 만 보내면 백엔드가 (email, gid) 로 멀티턴을 이어준다(프론트가 history 를 동봉하지 않음).
 * error 이벤트/네트워크 실패는 fetchNDJSON 이 axios-shape 로 throw → 호출자가 getApiErrorMessage 처리.
 */
export const streamResearchChat = async (req: ResearchChatRequest, h: StreamHandlers): Promise<void> => {
  await fetchNDJSON<ResearchChatEvent>({
    url: BASE_URL,
    body: req,
    signal: h.signal,
    onChunk: (event) => {
      switch (event.type) {
        case "start":
        case "step":
        case "tool_parameters":
          h.onStatus?.(event.message);
          break;
        case "routing":
          // routing 은 사용자용 message 가 없어 상태문구 갱신 생략(step 이 진행을 표시).
          break;
        case "media":
          h.onSources?.(event.sources);
          break;
        case "response_chunk":
          h.onDelta(event.content);
          break;
        case "title":
          h.onTitle?.(event.content);
          break;
        case "follow_up_question":
          // content 는 후속질문 list 의 JSON 문자열 — 파싱 실패 시 무시.
          try {
            const parsed: unknown = JSON.parse(event.content);
            if (Array.isArray(parsed)) {
              h.onFollowUps?.(parsed.filter((q): q is string => typeof q === "string"));
            }
          } catch {
            // malformed follow_up_question payload — 무시
          }
          break;
        case "workflow_complete":
          // 정상 종료 신호 — 추가 액션 없음(스트림이 곧 done).
          break;
        // error 이벤트는 fetchNDJSON 이 이미 throw 하므로 여기 도달하지 않음.
      }
    },
  });
};
