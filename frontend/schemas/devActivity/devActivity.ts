// schemas/devActivity/devActivity.ts — 포트폴리오 활동 요약 챗 응답/요청 타입

// backend-service `schemas/chat/chat_schema.py` 의 ChatAccountInfo 와 lockstep.
// 원 생산자는 portfolio-mcp `AccountInfo` 이고 backend 가 뷰 모델로 매핑한다 (#368).
export interface AccountInfo {
  account_id: string; // 계좌·포트폴리오 식별자
  name: string; // 계좌 별칭 (portfolio-mcp account_name)
  kind: string; // 계좌 유형 — cash(위탁) | margin(신용) | isa | pension(연금) 등
  base_ccy: string; // 기준 통화 (KRW/USD …)
}

// backend-service ChatHolderInfo 와 lockstep. portfolio-mcp 에 계좌주 신원 필드가 없어
// 이 목록은 현재 항상 비어 있다 (#368).
export interface HolderInfo {
  account_id: string;
  name: string;
  email: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  question: string;
  account: string | null; // 좌측에서 선택한 단일 계좌·포트폴리오
  since?: string | null; // YYYY-MM-DD (조회기간 시작)
  until?: string | null;
  symbols?: string[]; // 종목 코드·티커 목록 (조회 범위 한정)
  holders?: string[]; // 계좌주 email
  kind?: string | null; // cash | margin | pension (자동탐색 범위)
  history?: ChatTurn[]; // 직전 대화 (멀티턴 — 서버 무상태, 매 요청 동봉)
}
