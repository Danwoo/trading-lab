// hooks/shared/useFileGroups.ts
import { useState, useEffect } from "react";
import { FileDetail } from "@/schemas/common/file";
import { useFileList } from "./useFileList";
import { showToast } from "@/components/shared/Feedback";

export interface FileConfig {
  key: string;
  fileId?: string;
}

export interface FileState {
  files: FileDetail[];
  isLoading: boolean;
}

/**
 * 여러 파일 그룹을 동시에 관리하는 훅
 */
export function useFileGroups(configs: FileConfig[]): Record<string, FileState>;
// eslint-disable-next-line no-redeclare
export function useFileGroups(configs: FileConfig[], simpleMode: true): Record<string, FileDetail[]>;
// eslint-disable-next-line no-redeclare
export function useFileGroups(
  configs: FileConfig[],
  simpleMode?: boolean,
): Record<string, FileState> | Record<string, FileDetail[]> {
  // 각 파일 그룹의 초기 상태 설정
  const initialStates: Record<string, FileState> = {};
  configs.forEach((config) => {
    initialStates[config.key] = { files: [], isLoading: false };
  });

  const [fileStates, setFileStates] = useState<Record<string, FileState>>(initialStates);
  const { loadFileList } = useFileList();

  useEffect(() => {
    const abortController = new AbortController();

    const loadFile = async (config: FileConfig) => {
      const { key, fileId } = config;

      // fileId가 없으면 빈 상태로 설정하고 종료
      if (!fileId) {
        setFileStates((prev) => ({
          ...prev,
          [key]: { files: [], isLoading: false },
        }));
        return;
      }

      // 파일 로딩 시작 - 로딩 상태 활성화
      setFileStates((prev) => ({
        ...prev,
        [key]: { ...prev[key], isLoading: true },
      }));

      try {
        const files = await loadFileList(fileId, { signal: abortController.signal });

        // 요청이 취소되지 않았을 때만 상태 업데이트
        if (!abortController.signal.aborted) {
          setFileStates((prev) => ({
            ...prev,
            [key]: { files, isLoading: false },
          }));
        }
      } catch (error) {
        // AbortError가 아닌 실제 에러만 처리
        if ((error as any).name !== "AbortError" && !abortController.signal.aborted) {
          showToast("파일 목록을 불러오지 못했습니다.", "error");
          setFileStates((prev) => ({
            ...prev,
            [key]: { files: [], isLoading: false },
          }));
        }
      }
    };

    // 모든 파일 그룹을 병렬로 로드
    Promise.all(configs.map((config) => loadFile(config)));

    // 컴포넌트 언마운트 시 진행 중인 요청 취소
    return () => abortController.abort();
  }, [configs.map((c) => `${c.key}:${c.fileId || ""}`).join("|"), loadFileList]);

  // simpleMode가 활성화된 경우 파일 배열만 추출하여 반환
  if (simpleMode) {
    const simpleResult: Record<string, FileDetail[]> = {};
    Object.entries(fileStates).forEach(([key, state]) => {
      simpleResult[key] = state.files;
    });
    return simpleResult;
  }

  // 기본 모드: 파일 배열과 로딩 상태를 모두 포함하여 반환
  return fileStates;
}
