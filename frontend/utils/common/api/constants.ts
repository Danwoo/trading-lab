export const OPERATION_SUCCESS_STATUS_CODES: Record<string, number> = {
  GET: 200,
  POST: 201,
  PUT: 200,
  PATCH: 200,
  DELETE: 200,
};

export const OPERATION_SUCCESS_MESSAGES: Record<string, string> = {
  GET: "조회되었습니다.",
  POST: "등록이 완료되었습니다.",
  PUT: "수정이 완료되었습니다.",
  PATCH: "수정이 완료되었습니다.",
  DELETE: "삭제가 완료되었습니다.",
};

export const OPERATION_ERROR_MESSAGES: Record<string, string> = {
  GET: "데이터 조회 중 오류가 발생했습니다.",
  POST: "데이터 저장 중 오류가 발생했습니다.",
  PUT: "데이터 수정 중 오류가 발생했습니다.",
  PATCH: "데이터 수정 중 오류가 발생했습니다.",
  DELETE: "데이터 삭제 중 오류가 발생했습니다.",
  AUTH: "인증이 만료되었습니다.",
};
