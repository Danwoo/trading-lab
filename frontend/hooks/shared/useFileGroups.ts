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
  /**
   * 목록을 **못 읽었다**. `files: []` 와 다르다 — 빈 배열은 「없다」이고 이것은 「모른다」다.
   *
   * 종전에는 실패가 빈 배열로 접혀, 화면이 조회 실패를 「첨부된 파일이 없습니다」로 단언했다.
   * 파일은 있는데 사용자는 유실됐다고 믿고 다시 올리려 든다 (#440·B-10). 이 레포는 종목 검색에서
   * 같은 구분(`unavailable_reason` — 「없다」와 「아직 안 받았다」)을 이미 하고 있다.
   */
  error?: boolean;
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
    initialStates[config.key] = { files: [], isLoading: false, error: false };
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
            [key]: { files, isLoading: false, error: false },
          }));
        }
      } catch (error) {
        // AbortError가 아닌 실제 에러만 처리
        if ((error as any).name !== "AbortError" && !abortController.signal.aborted) {
          showToast("파일 목록을 불러오지 못했습니다.", "error");
          setFileStates((prev) => ({
            ...prev,
            // 빈 배열로 접지 않는다 — 화면이 「없다」와 「못 읽었다」를 갈라야 한다.
            [key]: { files: [], isLoading: false, error: true },
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
