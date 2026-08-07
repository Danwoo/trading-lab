import { env } from "@/env";
// services/common/fileService.ts
// 파일 서비스 관련 API 호출 모음

import { CreateOut, DeleteOut } from "@/schemas/common/types";
import { FileOut, FileListOut, FileDetailOut, FileDetailListOut, FilePreviewQuery } from "@/schemas/common/file";
import { apiCall, getClientToken, getExternalBaseUrl } from "@/utils/common/api/client";
import { useUploadProgressStore } from "@/stores/shared/uploadProgressStore";

// "/file-service" 는 흡수 후에도 유지되는 **외부 URL 경로**다 — nginx 가 이 세그먼트를 통합 앱으로
// 프록시한다(platform/nginx/config/nginx.conf). 서비스가 사라졌다고 지우면 업로드 경로가 끊긴다.
const getBaseUrl = () => getExternalBaseUrl(env.NEXT_PUBLIC_FILE_SERVICE_URL, "/file-service");

// 파일 바이너리를 Authorization 헤더로 받아 object URL 로 변환 — 토큰을 URL 쿼리에 노출하지 않음
const fetchObjectUrl = async (url: string, token: string | null): Promise<string> => {
  const blob = await apiCall<Blob>(url, { method: "GET", token, responseType: "blob" });
  if (!(blob instanceof Blob)) throw new Error("파일을 불러오지 못했습니다.");
  return URL.createObjectURL(blob);
};

/**
 * 파일 업로드
 * @param files 업로드할 File 배열
 * @param existingFileId 기존 첨부파일 ID (추가 업로드 시)
 * @returns 생성 결과 (CreateOut) 또는 null
 */
export const uploadFiles = async (files: File[], existingFileId?: string): Promise<CreateOut | null> => {
  if (files.length === 0) return null;

  const { startUpload, setProgress, finishUpload } = useUploadProgressStore.getState();
  startUpload();

  try {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    if (existingFileId) formData.append("atch_file_id", existingFileId);

    const token = await getClientToken();
    const result = await apiCall<CreateOut>(`${getBaseUrl()}/file`, {
      method: "POST",
      data: formData,
      token,
      onUploadProgress: (progressEvent: any) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percentCompleted);
        }
      },
    });

    finishUpload();
    return result;
  } catch (error) {
    finishUpload();
    throw error;
  }
};

/**
 * 파일 목록 조회 (DevExtreme 필터/정렬/페이지네이션)
 */
export const selectFileList = async (params: any): Promise<FileListOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  const token = await getClientToken();
  return apiCall<FileListOut>(`${getBaseUrl()}/file`, {
    method: "GET",
    params: queryParams,
    token,
  });
};

/**
 * 단일 파일 메타데이터 조회
 * @param data 첨부파일 ID 문자열 또는 객체
 * @param options AbortSignal 설정용 옵션
 * @returns 파일 정보 (FileOut) 또는 null
 */
export const selectFile = async (
  data: string | { atch_file_id: string },
  options?: { signal?: AbortSignal },
): Promise<FileOut | null> => {
  const atch_file_id = typeof data === "string" ? data : data.atch_file_id;
  const token = await getClientToken();

  return apiCall<FileOut>(`${getBaseUrl()}/file/${atch_file_id}`, {
    method: "GET",
    signal: options?.signal,
    token,
  });
};

/**
 * 첨부파일 내 모든 파일 삭제
 * @param atch_file_id 첨부파일 ID
 * @param options AbortSignal 설정용 옵션
 * @returns 삭제 결과 (DeleteOut) 또는 null
 */
export const deleteAllFiles = async (
  atch_file_id: string,
  options?: { signal?: AbortSignal },
): Promise<DeleteOut | null> => {
  const token = await getClientToken();
  return apiCall<DeleteOut>(`${getBaseUrl()}/file/${atch_file_id}`, {
    method: "DELETE",
    signal: options?.signal,
    token,
  });
};

/**
 * 첨부파일 상세 목록 조회
 * @param atch_file_id 첨부파일 ID
 * @param options AbortSignal 설정용 옵션
 * @returns 파일 상세 목록 (FileDetailListOut) 또는 null
 */
export const selectFileDetailList = async (
  atch_file_id: string,
  options?: { signal?: AbortSignal },
): Promise<FileDetailListOut | null> => {
  const token = await getClientToken();
  return apiCall<FileDetailListOut>(`${getBaseUrl()}/file/${atch_file_id}/detail`, {
    method: "GET",
    signal: options?.signal,
    token,
  });
};

/**
 * 특정 파일 상세 정보 조회
 * @param atch_file_id 첨부파일 ID
 * @param file_sn 파일 일련번호
 * @param options AbortSignal 설정용 옵션
 * @returns 파일 상세 (FileDetailOut) 또는 null
 */
export const selectFileDetail = async (
  atch_file_id: string,
  file_sn: number,
  options?: { signal?: AbortSignal },
): Promise<FileDetailOut | null> => {
  const token = await getClientToken();
  return apiCall<FileDetailOut>(`${getBaseUrl()}/file/${atch_file_id}/detail/${file_sn}`, {
    method: "GET",
    signal: options?.signal,
    token,
  });
};

/**
 * 특정 파일 삭제
 * @param atch_file_id 첨부파일 ID
 * @param file_sn 파일 일련번호
 * @param options AbortSignal 설정용 옵션
 * @returns 삭제 결과 (DeleteOut) 또는 null
 */
export const deleteFile = async (
  atch_file_id: string,
  file_sn: number,
  options?: { signal?: AbortSignal },
): Promise<DeleteOut | null> => {
  const token = await getClientToken();
  return apiCall<DeleteOut>(`${getBaseUrl()}/file/${atch_file_id}/detail/${file_sn}`, {
    method: "DELETE",
    signal: options?.signal,
    token,
  });
};

/**
 * 파일 다운로드 object URL 생성 (Authorization 헤더로 blob 요청)
 * @param atch_file_id 첨부파일 ID
 * @param file_sn 파일 일련번호 (기본값 0)
 * @returns object URL 문자열 (blob:)
 */
export const selectFileDownloadUrl = async (atch_file_id: string, file_sn: number = 0): Promise<string> => {
  const token = await getClientToken();
  const base = `${getBaseUrl()}/file/${atch_file_id}/detail/${file_sn}/download`;
  return fetchObjectUrl(base, token);
};

/**
 * 파일 미리보기 object URL 생성 (Authorization 헤더로 blob 요청)
 * @param atch_file_id 첨부파일 ID
 * @param file_sn 파일 일련번호 (기본값 0)
 * @param q 미리보기 컷/크롭 옵션
 * @returns object URL 문자열 (blob:)
 */
export const selectFilePreviewUrl = async (
  atch_file_id: string,
  file_sn: number = 0,
  q?: FilePreviewQuery,
): Promise<string> => {
  const token = await getClientToken();
  const base = `${getBaseUrl()}/file/${atch_file_id}/detail/${file_sn}/preview`;

  const sp = new URLSearchParams();
  if (q?.size != null) sp.set("size", String(q.size));
  if (q?.x1 != null) sp.set("x1", String(q.x1));
  if (q?.y1 != null) sp.set("y1", String(q.y1));
  if (q?.x2 != null) sp.set("x2", String(q.x2));
  if (q?.y2 != null) sp.set("y2", String(q.y2));

  const qs = sp.toString();
  return fetchObjectUrl(qs ? `${base}?${qs}` : base, token);
};
