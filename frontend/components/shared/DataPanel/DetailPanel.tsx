"use client";

import { useEffect, useState } from "react";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast, showMessage } from "@/components/shared/Feedback";
// `Loading` 은 Feedback 배럴에서 빠졌다 — 배럴을 devextreme 에서 떼어내기 위해서다
// (#381, `Feedback/index.ts` 주석).
import { Loading } from "@/components/shared/Feedback/Loading";
import { useUploadProgressStore } from "@/stores/shared/uploadProgressStore";

type ModeType = "view" | "edit" | "create";

interface Props<T, F> {
  title?: React.ReactNode;
  data: T | null;
  initialMode: "view" | "create";
  isSelectLoading?: boolean;
  ViewComponent: React.ComponentType<any>;
  FormComponent?: React.ComponentType<any>;
  viewProps?: any;
  formProps?: any;
  defaultFormData?: Partial<F>;
  onComplete?: (data: T | null, action?: "create" | "update" | "delete") => void;
  apiService?: {
    select: (data: any) => Promise<T | null>;
    create?: (data: any) => Promise<any>;
    update?: (data: any) => Promise<any>;
    delete?: (data: any) => Promise<any>;
  };
}

export function DetailPanel<T, F>({
  title,
  data,
  initialMode,
  isSelectLoading = false,
  ViewComponent,
  FormComponent,
  viewProps = {},
  formProps = {},
  defaultFormData,
  onComplete,
  apiService,
}: Props<T, F>) {
  const [mode, setMode] = useState<ModeType>(initialMode);
  const [currentData, setCurrentData] = useState<T | null>(data);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const { isUploading, progress } = useUploadProgressStore();

  useEffect(() => {
    setCurrentData(data);
    setMode(initialMode);
    setRefreshKey((prev) => prev + 1);
  }, [data, initialMode]);

  const handleEdit = async (): Promise<boolean> => {
    if (!data || !apiService || !FormComponent) return false;

    setIsLoading(true);
    try {
      const latest = await apiService.select(data);
      setCurrentData(latest);
      setMode("edit");
      return true;
    } catch (error) {
      showToast(getApiErrorMessage(error), "error");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (): Promise<boolean> => {
    if (!data) {
      setMode("view");
      return true;
    }

    if (!apiService) {
      setMode("view");
      return true;
    }

    setIsLoading(true);
    try {
      const latest = await apiService.select(data);
      setCurrentData(latest);
      setMode("view");
      return true;
    } catch (error) {
      showToast(getApiErrorMessage(error), "error");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (submitData: F): Promise<boolean> => {
    if (!apiService || !FormComponent) return false;
    if (isLoading) return false;

    setIsLoading(true);

    try {
      let result: any = null;

      if (mode === "create" && apiService.create) {
        result = await apiService.create(submitData);
        const latest = await apiService.select(result.data);
        showToast(result?.message || "등록이 완료되었습니다.", "success");
        onComplete?.(latest, "create");
        setMode("view");
        return true;
      } else if (mode === "edit" && apiService.update) {
        result = await apiService.update(submitData);
        const latest = await apiService.select(data as any);
        showToast(result?.message || "수정이 완료되었습니다.", "success");
        onComplete?.(latest, "update");
        setMode("view");
        return true;
      }

      return false;
    } catch (error: any) {
      if (error?.response?.status === 422) {
        throw error;
      }
      showToast(getApiErrorMessage(error), "error");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!currentData || !apiService || !apiService.delete) return;

    showMessage("삭제 확인", <div>정말 삭제하시겠습니까?</div>, {
      type: "confirm",
      confirmText: "삭제",
      cancelText: "취소",
      callback: {
        onConfirm: async () => {
          setIsLoading(true);
          try {
            const result = await apiService.delete!(currentData);
            showToast(result?.message || "삭제가 완료되었습니다.", "success");
            onComplete?.(null, "delete");
          } catch (error) {
            showToast(getApiErrorMessage(error), "error");
          } finally {
            setIsLoading(false);
          }
        },
      },
    });
  };

  return (
    <div id="detailPanel" className="h-full relative flex flex-col">
      <Loading
        visible={isUploading || isSelectLoading || isLoading}
        message={isUploading ? (progress === 100 ? "서버 처리 중..." : `업로드 중... ${progress}%`) : "Loading..."}
        shading={true}
        shadingColor={isUploading ? "rgba(0,0,0,0.3)" : "rgba(0,0,0,0)"}
      />

      <div className="flex-shrink-0 p-2 pb-0">
        <h2 className="text-lg text-gray-700">📄 {title}</h2>
      </div>

      <div className="flex-1 min-h-0 overflow-auto py-2 px-2">
        {mode === "view" && currentData && (
          <ViewComponent
            key={refreshKey}
            data={currentData}
            onEdit={handleEdit}
            onDelete={handleDelete}
            {...viewProps}
          />
        )}

        {apiService && FormComponent && (mode === "edit" || mode === "create") && (
          <FormComponent
            key={mode}
            isNew={mode === "create"}
            initialData={mode === "create" ? (defaultFormData ?? {}) : currentData || {}}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            {...formProps}
          />
        )}

        {mode === "view" && !currentData && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <div className="text-4xl mb-4">📋</div>
              <div className="text-lg mb-2">데이터가 없습니다</div>
              <div className="text-sm">항목을 선택하거나 등록 버튼을 클릭하세요.</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
