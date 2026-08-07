// schemas/researchDocument/researchDocument.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { StrRange, files, object } from "@/lib/zod/helpers";

// 백엔드 계약: backend-service /research-document (슬라이스 B, PR #168)
//   POST body {atch_file_id, file_sn, doc_title} → 업로드된 파일을 POST 안에서 동기 색인
//     완료 후 컨벤션대로 CreateOut(data={research_doc_id})(pk)만 반환. 잡 큐 아님 —
//     status·chunk_count 등 색인 결과 상세는 이 pk 로 GET/{id} 를 이어 호출해 읽는다.
//   GET(목록 {items, total_count}), GET/{id}, DELETE/{id}
//   ResearchDocumentOut{research_doc_id, atch_file_id, file_sn, doc_title,
//                       status(indexed|mock-indexed|empty|failed|uploaded), chunk_count, + 공통(reg_dt...)}
//   PUT(수정) 없음 — 문서는 등록·삭제만, 재색인은 삭제 후 재업로드.

// 색인 상태 — 백엔드가 내려주는 고정 enum (공통코드 아님).
//   indexed=색인완료, mock-indexed=MOCK 모드(파싱·청킹만, 검색 불가), empty=텍스트없음,
//   failed=실패, uploaded=대기(색인 전)
export type ResearchDocumentStatus = "indexed" | "mock-indexed" | "empty" | "failed" | "uploaded";

export const RESEARCH_DOCUMENT_STATUS_LABELS: Record<string, string> = {
  indexed: "색인완료",
  "mock-indexed": "모의색인(검색불가)",
  empty: "텍스트없음",
  failed: "실패",
  uploaded: "대기",
};

export const getResearchDocumentStatusLabel = (status?: string): string =>
  (status ? RESEARCH_DOCUMENT_STATUS_LABELS[status] : undefined) ?? status ?? "-";

// 생성 입력 — doc_title 만 사용자 입력, 파일은 업로더가 선택(업로드 후 atch_file_id·file_sn 로 치환).
//   z.object 가 미지 키를 제거하므로 researchFiles 는 스키마에 명시해야 검증을 통과한다(#161 패턴).
//   files() 는 min(1) 이라 문서에는 파일 1개가 필수다.
export const ResearchDocumentCreateInSchema = object({
  doc_title: StrRange(1, 500),
  researchFiles: files(),
});

export type ResearchDocumentCreateIn = z.infer<typeof ResearchDocumentCreateInSchema>;

// 출력(목록/단건) — research_doc_id 는 색인 시 백엔드가 생성
export interface ResearchDocumentOut extends CommonEntity {
  research_doc_id: number;
  atch_file_id?: string;
  file_sn?: number;
  doc_title: string;
  status: ResearchDocumentStatus;
  chunk_count?: number;
}

export interface ResearchDocumentsOut {
  items: ResearchDocumentOut[];
  total_count: number;
}
