// components/shared/DataPanel/DetailGridPanel.tsx
"use client";

import React, { useMemo, useState, useCallback, useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { Button } from "@/components/shared/ui/Button";
import type { ActionButton } from "@/components/shared/ui";
import { FormModal } from "@/components/shared/Layout";
import { DetailGrid } from "@/components/shared/DataGrid";
import { useDetailGridData } from "@/hooks/shared/useDetailGridData";
import { useDetailGridActions } from "@/hooks/shared/useDetailGridActions";
import { useDetailModal } from "@/hooks/shared/useDetailModal";
import { useFormState } from "@/hooks/shared/useFormState";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { WriteAccessNotice } from "@/components/shared/Feedback/WriteAccessNotice";
import { withWriteDeniedHint } from "@/constants/writeAccess";

const BUILTIN_CRUD_ICONS = new Set(["plus", "edit", "trash"]);

interface Props<T> {
  fetchGrid: (params?: any) => Promise<{ items: T[]; total_count: number } | null>;
  columns: LegacyGridColumn[];
  keyField?: string;
  editable?: boolean;
  clientSidePaging?: boolean;
  showPaging?: boolean;
  height?: string;
  inactiveExpr?: string;
  showRefreshButton?: boolean;
  apiService?: {
    create?: (data: T) => Promise<{ message?: string } | void>;
    update?: (data: T) => Promise<{ message?: string } | void>;
    delete?: (data: T) => Promise<{ message?: string } | void>;
  };
  FormComponent?: React.ComponentType<any>;
  defaultFormData?: Partial<T>;
  formProps?: any;
  formWidth?: number | string;
  formHeight?: number | string;
  formMinWidth?: number | string;
  formMinHeight?: number | string;
  formMaxWidth?: number | string;
  formMaxHeight?: number | string;
  extraFormContent?: (props: {
    formData: T;
    onFieldChange: (field: string, value: any) => void;
    isOpen: boolean;
    modalMode: "create" | "edit";
  }) => React.ReactNode;
  customActions?: ActionButton[];
  /**
   * 역할이 이 격자의 쓰기를 막고 있다 (#341). 주면 등록·수정·삭제 아이콘이 **비활성**으로
   * 서고(사라지지 않는다 — 있는 기능을 감추면 없는 것으로 읽힌다) 격자 머리에서 사유를 말한다.
   * `DetailPanel` 의 같은 이름 prop 과 같은 규율이다: 판정은 부르는 쪽이 한다.
   */
  writeGated?: { halted: string[] };
  onSelectionChanged?: (item: T) => void;
  onRowDblClick?: (item: T) => void;
  onDataChanged?: () => void;
  onDataLoaded?: (data: { items: T[]; total_count: number }) => void;
}

export interface DetailGridPanelRef {
  refresh: () => void;
}

const DetailGridPanelComponent = <T,>(
  {
    fetchGrid,
    columns,
    keyField = "rn",
    editable = true,
    clientSidePaging = false,
    showPaging = true,
    height = "100%",
    inactiveExpr,
    showRefreshButton = true,
    apiService,
    FormComponent,
    defaultFormData = {},
    formProps = {},
    formWidth = 800,
    formHeight,
    formMinWidth,
    formMinHeight,
    formMaxWidth,
    formMaxHeight = "95vh",
    extraFormContent,
    customActions = [],
    writeGated,
    onSelectionChanged,
    onRowDblClick,
    onDataChanged,
    onDataLoaded,
  }: Props<T>,
  ref: React.Ref<DetailGridPanelRef>,
) => {
  const [dataVersion, setDataVersion] = useState(0);

  const handleFetchGrid = useCallback(
    async (params?: any) => {
      const result = await fetchGrid(clientSidePaging ? {} : params);
      if (!result) {
        const emptyResult = { items: [], total_count: 0 };
        onDataLoaded?.(emptyResult);
        return emptyResult;
      }

      if (clientSidePaging) {
        const items = result.items || [];
        const clientResult = { items, total_count: items.length };
        onDataLoaded?.(clientResult);
        return clientResult;
      } else {
        const serverResult = {
          items: result.items || [],
          total_count: result.total_count || 0,
        };
        onDataLoaded?.(serverResult);
        return serverResult;
      }
    },
    [fetchGrid, clientSidePaging, onDataLoaded],
  );

  const handleDataChanged = useCallback(() => {
    if (clientSidePaging) {
      setDataVersion((prev) => prev + 1);
    }
    onDataChanged?.();
  }, [clientSidePaging, onDataChanged]);

  const { dataSource, selectedData, handleSelect, handleComplete } = useDetailGridData({
    fetchGrid: handleFetchGrid,
    onDataChanged: handleDataChanged,
    keyField,
    // 클라이언트 페이징이면 전체를 한 번 받아 로컬에서 정렬·필터한다 — 위 handleFetchGrid 가
    // 그 모드에서 서버로 skip/take/sort/filter 를 아예 안 보내므로, 서버 모드로 두면 정렬·필터가
    // 조용히 아무 일도 하지 않는다.
    paginate: !clientSidePaging,
    dependencies: clientSidePaging ? [dataVersion] : undefined,
  });

  useImperativeHandle(
    ref,
    () => ({
      refresh: () => handleComplete(),
    }),
    [handleComplete],
  );

  const { isModalOpen, modalMode, openCreateModal, openEditModal, closeModal, getInitialFormData } =
    useDetailModal(selectedData);

  const initialFormData = useMemo(() => getInitialFormData(defaultFormData), [getInitialFormData, defaultFormData]);
  const { formData, handleFieldChange, getFieldProps, handleSubmit, resetForm } = useFormState<T>(initialFormData);

  const initialFormDataRef = useRef(initialFormData);
  useEffect(() => {
    initialFormDataRef.current = initialFormData;
  });

  const prevIsModalOpenRef = useRef(false);
  useEffect(() => {
    const wasOpen = prevIsModalOpenRef.current;
    prevIsModalOpenRef.current = isModalOpen;
    if (isModalOpen && !wasOpen) {
      resetForm(initialFormDataRef.current);
    }
  }, [isModalOpen, resetForm]);

  const handleFieldChangeWrapper = useCallback(
    (field: string, value: any) => {
      handleFieldChange(field as keyof T, value);
    },
    [handleFieldChange],
  );

  const handleDelete = useCallback(async () => {
    if (!selectedData || !apiService?.delete) {
      showToast("삭제할 항목을 선택해주세요.", "warning");
      return;
    }

    showMessage("삭제 확인", <div>정말 삭제하시겠습니까?</div>, {
      type: "confirm",
      confirmText: "삭제",
      cancelText: "취소",
      callback: {
        onConfirm: async () => {
          try {
            const result = await apiService.delete!(selectedData);
            showToast(result?.message || "삭제가 완료되었습니다.", "success");
            handleComplete();
          } catch (error) {
            showToast(getApiErrorMessage(error), "error");
          }
        },
      },
    });
  }, [selectedData, apiService, handleComplete]);

  const handleSave = useCallback(() => {
    if (!apiService) return;
    handleSubmit(async (data: T) => {
      try {
        let result: any = null;
        if (modalMode === "create") {
          if (apiService.create) {
            result = await apiService.create(data);
            showToast(result?.message || "등록이 완료되었습니다.", "success");
          } else return false;
        } else {
          if (apiService.update) {
            result = await apiService.update(data);
            showToast(result?.message || "수정이 완료되었습니다.", "success");
          } else return false;
        }
        closeModal();
        handleComplete();
        return true;
      } catch (error: any) {
        if (error?.response?.status === 422) throw error;
        showToast(getApiErrorMessage(error), "error");
        return false;
      }
    });
  }, [handleSubmit, modalMode, apiService, closeModal, handleComplete]);

  const handleSelectionChanged = useCallback(
    (item: T | null) => {
      handleSelect(item);
      if (item && onSelectionChanged) onSelectionChanged(item);
    },
    [handleSelect, onSelectionChanged],
  );

  const buttons = useDetailGridActions({
    onRefresh: handleComplete,
    onCreate: apiService?.create ? openCreateModal : undefined,
    onEdit: apiService?.update ? openEditModal : undefined,
    onDelete: apiService?.delete ? handleDelete : undefined,
    selectedData,
    customActions,
  });

  const visibleButtons = buttons
    .filter((button) => {
      if (button.visible === false) return false;
      if (BUILTIN_CRUD_ICONS.has(button.icon ?? "")) return editable;
      if (button.icon === "refresh") return editable || showRefreshButton;
      return true; // customActions는 editable 무관하게 표시
    })
    // 새로고침은 읽기라 그대로 둔다 — 막힌 것만 막힌 것으로 보인다.
    .map((button) =>
      writeGated && BUILTIN_CRUD_ICONS.has(button.icon ?? "")
        ? { ...button, disabled: true, hint: withWriteDeniedHint(button.hint) }
        : button,
    );

  return (
    <div className="detail-grid-container flex flex-col" style={{ height }}>
      {writeGated && <WriteAccessNotice halted={writeGated.halted} className="mb-2" />}

      {visibleButtons.length > 0 && (
        <div className="flex-shrink-0 flex justify-end items-center mb-3">
          <div className="flex gap-2">
            {visibleButtons.map((button, index) => {
              const { visible, sort: _sort, ...buttonProps } = button;
              return <Button key={index} width={button.width || 40} hint={button.hint} {...buttonProps} />;
            })}
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0">
        <DetailGrid<T>
          dataSource={dataSource}
          columns={columns}
          height="100%"
          onSelectionChanged={handleSelectionChanged}
          onRowDblClick={onRowDblClick}
          selectedData={selectedData}
          showPaging={showPaging}
          inactiveExpr={inactiveExpr}
        />
      </div>

      {editable && !writeGated && apiService && FormComponent && (apiService.create || apiService.update) && (
        <FormModal
          visible={isModalOpen}
          title={modalMode === "create" ? "등록" : "수정"}
          width={formWidth}
          height={formHeight}
          minWidth={formMinWidth}
          minHeight={formMinHeight}
          maxWidth={formMaxWidth}
          maxHeight={formMaxHeight}
          onClose={closeModal}
          onSave={handleSave}
          saveDisabled={(modalMode === "create" && !apiService.create) || (modalMode === "edit" && !apiService.update)}
        >
          {isModalOpen && (
            <FormComponent
              formData={formData}
              modalMode={modalMode}
              onFieldChange={handleFieldChangeWrapper}
              getFieldProps={getFieldProps}
              {...formProps}
            />
          )}
        </FormModal>
      )}

      {extraFormContent?.({
        formData: formData as T,
        onFieldChange: handleFieldChangeWrapper,
        isOpen: isModalOpen,
        modalMode,
      })}
    </div>
  );
};

export const DetailGridPanel = forwardRef(DetailGridPanelComponent) as <T>(
  props: Props<T> & { ref?: React.Ref<DetailGridPanelRef> },
) => React.ReactElement;

(DetailGridPanel as any).displayName = "DetailGridPanel";
