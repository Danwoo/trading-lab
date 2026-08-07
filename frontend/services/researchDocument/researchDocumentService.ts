import { CreateOut, DeleteOut } from "@/schemas/common/types";
import {
  ResearchDocumentCreateInSchema,
  ResearchDocumentsOut,
  ResearchDocumentOut,
} from "@/schemas/researchDocument/researchDocument";
import { apiCall } from "@/utils/common/api/client";
import { uploadFiles } from "@/services/common/fileService";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/research-document"
const BASE_URL = "/api/external/backend/research-document";

const stringifyGridParams = (params: any): Record<string, any> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);
  return queryParams;
};

// 리서치 문서 목록 조회
export const selectResearchDocumentList = async (params: any): Promise<ResearchDocumentsOut | null> => {
  return apiCall<ResearchDocumentsOut>(BASE_URL, { method: "GET", params: stringifyGridParams(params) });
};

// 리서치 문서 단건 조회
export const selectResearchDocument = async (data: any): Promise<ResearchDocumentOut | null> => {
  return apiCall<ResearchDocumentOut>(`${BASE_URL}/${data.research_doc_id}`, { method: "GET" });
};

// 리서치 문서 등록
// Zod 검증 → 파일 업로드(atch_file_id·file_sn 확보) → 색인 요청(POST) 순서 (#161 패턴)
export const createResearchDocument = async (data: any): Promise<CreateOut | null> => {
  try {
    const { researchFiles, ...validatedData } = validateWithZod(ResearchDocumentCreateInSchema, data);

    const uploadResult = await uploadFiles(researchFiles, undefined);
    const atch_file_id = uploadResult?.data?.atch_file_id;
    const file_sn = uploadResult?.data?.uploaded_files?.[0]?.file_sn;

    return apiCall<CreateOut>(BASE_URL, {
      method: "POST",
      data: { ...validatedData, atch_file_id, file_sn },
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// 리서치 문서 삭제 — 백엔드 DELETE 한 번으로 청크 회수·파일 삭제·레코드 삭제까지 처리한다.
//   프론트가 파일을 선행 삭제하지 않는다: 백엔드가 존재·소유 검증 후 file 모듈 파일 삭제를
//   포함해 원자적으로 수행하므로, 프론트 선행 삭제는 이중 삭제이자 검증 우회다.
export const deleteResearchDocument = async (data: any): Promise<DeleteOut | null> => {
  const { research_doc_id } = data;

  return apiCall<DeleteOut>(`${BASE_URL}/${research_doc_id}`, { method: "DELETE" });
};
