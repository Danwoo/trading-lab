// hooks/shared/useFileList.ts
import { useCallback } from "react";
import { FileDetail } from "@/schemas/common/file";
import { selectFileDetailList, selectFileDownloadUrl } from "@/services/common/fileService";

export const useFileList = () => {
  const loadFileList = useCallback(
    async (atchFileId?: string, options?: { signal?: AbortSignal }): Promise<FileDetail[]> => {
      if (!atchFileId) return [];

      try {
        // selectFileDetailList에 AbortSignal 전달
        const response = await selectFileDetailList(atchFileId, options);
        if (!response) {
          return [];
        }

        // 요청이 취소되었는지 확인
        if (options?.signal?.aborted) {
          throw new Error("AbortError");
        }

        // 비동기 map 처리 - Promise.all 사용
        const processedFiles = await Promise.all(
          (response.items || []).map(async (file) => {
            // 각 파일의 URL을 비동기로 생성
            const url = await selectFileDownloadUrl(file.atch_file_id, file.file_sn);

            return {
              ...file,
              id: file.file_sn.toString(),
              name: file.orignl_file_nm,
              size: file.file_mg,
              url: url,
            };
          }),
        );

        return processedFiles;
      } catch (error) {
        // AbortError는 다시 throw해서 상위에서 처리
        if ((error as any).name === "AbortError" || (error as Error).message === "AbortError") {
          throw error;
        }
        return [];
      }
    },
    [],
  );

  return { loadFileList };
};
