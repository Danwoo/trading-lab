// hooks/shared/useDetailModal.ts
import { useState, useCallback } from "react";
import { showToast } from "@/components/shared/Feedback";

/**
 * 디테일 그리드 모달 상태 관리 훅
 */
export function useDetailModal<T>(selectedData: T | null) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | "edit">("create");

  const openCreateModal = useCallback(() => {
    setModalMode("create");
    setIsModalOpen(true);
  }, []);

  const openEditModal = useCallback(() => {
    if (!selectedData) {
      showToast("수정할 항목을 선택해주세요.", "warning");
      return;
    }
    setModalMode("edit");
    setIsModalOpen(true);
  }, [selectedData]);

  const closeModal = useCallback(() => {
    setIsModalOpen(false);
  }, []);

  // 초기 폼 데이터 생성
  const getInitialFormData = useCallback(
    (defaultData: Partial<T> = {}) => {
      if (modalMode === "create") {
        return defaultData;
      }
      return selectedData || {};
    },
    [modalMode, selectedData],
  );

  return {
    isModalOpen,
    modalMode,
    openCreateModal,
    openEditModal,
    closeModal,
    getInitialFormData,
  } as const;
}
