// schemas/researchChat/researchChat.ts
// #160 슬라이스 D-나: 투자리서치 챗 — 요청/이벤트/세션 타입.
// 백엔드: multi-agent-service /agent/example-ai (ai-chatbot 프론트 호환, NDJSON).
//   - 요청 스키마     : ExampleAIQueryIn (agent_schema.py)
//   - 이벤트 빌더     : example_ai_events.py (type 별 판별 유니온)
//   - sources 스키마  : _mk_source (example_ai_events.py)

/**
 * /agent/example-ai 요청 바디. 백엔드 ExampleAIQueryIn 대응.
 * switch1~5 는 MCP 스코프 토글 (생략 시 백엔드 기본값 전부 true = 전체 멀티에이전트).
 * D4(전체 멀티에이전트) 확정: v1 은 switch 를 생략해 웹·시세·공시·뉴스 + 문서 근거를 함께 라우팅.
 * DB/API payload key 라 snake_case 유지 (룰3: payload key 는 snake_case).
 */
export interface ResearchChatRequest {
  gid: number;
  question: string;
  switch1?: boolean; // web
  switch2?: boolean; // market-data
  switch3?: boolean; // disclosure
  switch4?: boolean; // news
  switch5?: boolean; // doc-search (업로드 리서치 문서)
}

/**
 * 근거 카드 1건. 백엔드 _mk_source 스키마 그대로 (payload key snake_case 없음 — 전부 flat 문자열 필드).
 * - url === ""  : 업로드 리서치 문서(domain="사내 리서치자료", title=file_nm) — 직링크 없음, 정적 카드.
 * - url 존재    : 웹/뉴스/공시/시세 — 클릭 가능 링크.
 */
export interface ResearchSource {
  title: string;
  tool: string;
  url: string;
  domain: string;
  content: string;
  thumbnail: string;
  favicon: string;
}

/**
 * /agent/example-ai NDJSON 이벤트 판별 유니온. 각 멤버는 example_ai_events.py 빌더와 필드 일치.
 * type 리터럴로 판별 (discriminated union).
 */
export type ResearchChatEvent =
  | { type: "start"; message: string; query: string }
  | { type: "step"; step: string; message: string; tools?: string[] }
  | {
      type: "routing";
      is_fiber_related: boolean;
      selected_tools: string[];
      tool_info: Array<Record<string, string>>;
    }
  | { type: "tool_parameters"; message: string; tools_with_keywords: Array<Record<string, string>> }
  | {
      type: "media";
      images: unknown[];
      sources: ResearchSource[];
      tool_results_summary: Record<string, unknown>;
    }
  | { type: "response_chunk"; content: string; chunk_id: number; accumulated_length: number }
  | { type: "title"; content: string }
  | { type: "follow_up_question"; content: string } // content = 후속질문 list 의 JSON 문자열
  | { type: "workflow_complete"; message: string }
  | { type: "error"; message: string };

/** 화면에 표시되는 대화 메시지 1건 (프론트 소유 트랜스크립트). */
export interface ResearchMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ResearchSource[]; // assistant 답변의 근거 카드 (media 이벤트)
  followUps?: string[]; // assistant 답변의 후속질문 (follow_up_question 이벤트)
}

/**
 * 대화 세션 1건. gid 는 프론트가 생성한 정수 (Date.now()).
 * 백엔드는 (email, gid) 로 히스토리를 서버 보관하지만 조회 API 가 없어(§1.2)
 * 표시 트랜스크립트는 프론트가 소유·영속(localStorage, D1)한다.
 */
export interface ResearchSession {
  gid: number;
  title: string; // 백엔드 title 이벤트로 자동 채움 (없으면 "새 대화")
  messages: ResearchMessage[];
  createdAt: number;
}
