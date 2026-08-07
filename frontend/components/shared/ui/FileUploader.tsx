// components/shared/ui/FileUploader.tsx
"use client";

import React, {
  useCallback,
  useState,
  forwardRef,
  useImperativeHandle,
  useMemo,
  useEffect,
  useRef,
  useId,
} from "react";
import { Button } from "@/components/shared/ui/Button";
import { FileTypeIcon } from "@/components/shared/ui/primitives/FileTypeIcon";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { FileDetail } from "@/schemas/common/file";
import { deleteFile } from "@/services/common/fileService";
import { useFileGroups } from "@/hooks/shared/useFileGroups";
import { formatFileSize } from "@/utils/common/fileUtils";

interface Props {
  atchFileId?: string;
  multiple?: boolean;
  maxFileSize?: number;
  maxFileCount?: number;
  allowedFileExtensions?: string[];
  selectButtonText?: string;
  labelText?: string;
  fileType?: "image" | "document" | "all";
  fieldName?: string;
  getFieldProps?: (fieldName: string) => any;
  onFilesChanged?: (files: File[]) => void;
  showFileList?: boolean;
}

export interface FileUploaderRef {
  selectFiles: () => File[];
  clearFiles: () => void;
  removeFile: (index: number) => void;
  hasExistingFiles: () => boolean;
}

/**
 * 파일 업로더 컴포넌트
 */
export const FileUploader = forwardRef<FileUploaderRef, Props>(
  (
    {
      atchFileId,
      multiple = false,
      maxFileSize = 1024 * 1024 * 1024,
      maxFileCount,
      allowedFileExtensions,
      selectButtonText = "파일 선택",
      labelText,
      fileType = "all",
      fieldName,
      getFieldProps,
      onFilesChanged,
      showFileList: showFileListProp = true,
    },
    ref,
  ) => {
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [deletingFiles, setDeletingFiles] = useState<Set<number>>(new Set());
    const [currentFileDetails, setCurrentFileDetails] = useState<FileDetail[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const inputId = useId();

    const fileGroupsConfig = useMemo(() => (atchFileId ? [{ key: "files", fileId: atchFileId }] : []), [atchFileId]);
    const fileGroups = useFileGroups(fileGroupsConfig);

    useEffect(() => {
      if (fileGroups.files?.files) {
        setCurrentFileDetails(fileGroups.files.files);
      }
    }, [fileGroups.files?.files]);

    const effectiveMaxFileCount = useMemo(() => {
      if (!multiple) return 1;
      return maxFileCount ?? Infinity;
    }, [multiple, maxFileCount]);

    const canAddMore = useMemo(() => {
      return currentFileDetails.length + selectedFiles.length < effectiveMaxFileCount;
    }, [currentFileDetails.length, selectedFiles.length, effectiveMaxFileCount]);

    const getFileTypeSettings = useCallback(() => {
      if (allowedFileExtensions && allowedFileExtensions.length > 0) {
        return {
          accept: allowedFileExtensions.join(","),
          allowedFileExtensions,
          labelText: labelText || "파일을 드래그하거나 클릭하세요",
        };
      }

      const extensionMap: Record<string, string[]> = {
        image: [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        document: [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".parquet"],
        all: [],
      };

      const labelMap: Record<string, string> = {
        image: "이미지 파일을 드래그하거나 클릭하세요",
        document: "문서 파일을 드래그하거나 클릭하세요",
        all: "파일을 드래그하거나 클릭하세요",
      };

      const extensions = extensionMap[fileType] || extensionMap.all;

      return {
        accept: extensions.length > 0 ? extensions.join(",") : "*",
        allowedFileExtensions: extensions,
        labelText: labelText || labelMap[fileType] || labelMap.all,
      };
    }, [allowedFileExtensions, labelText, fileType]);

    const fileSettings = useMemo(() => getFileTypeSettings(), [getFileTypeSettings]);

    useImperativeHandle(ref, () => ({
      selectFiles: () => selectedFiles,
      clearFiles: () => {
        setSelectedFiles([]);
        onFilesChanged?.([]);
      },
      removeFile: (index: number) => {
        const updated = selectedFiles.filter((_, i) => i !== index);
        setSelectedFiles(updated);
        onFilesChanged?.(updated);
      },
      hasExistingFiles: () => currentFileDetails.length > 0,
    }));

    const handleFilesPicked = useCallback(
      (picked: FileList | File[] | null) => {
        const files = picked ? Array.from(picked) : [];

        if (files.length === 0) {
          setSelectedFiles([]);
          onFilesChanged?.([]);
          return;
        }

        // DevExtreme 위젯이 하던 검증을 여기서 한다 — `accept` 는 파일 선택창의 필터일 뿐이라
        // 드래그&드롭이나 "모든 파일" 선택으로 얼마든지 우회된다(브라우저 공통).
        const rejected: string[] = [];
        const accepted = files.filter((file) => {
          if (file.size > maxFileSize) {
            rejected.push(`${file.name} (용량 초과)`);
            return false;
          }
          const allowed = fileSettings.allowedFileExtensions;
          if (allowed.length > 0) {
            const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
            if (!allowed.some((entry) => entry.toLowerCase() === ext)) {
              rejected.push(`${file.name} (허용되지 않는 형식)`);
              return false;
            }
          }
          return true;
        });
        if (rejected.length > 0) showToast(`업로드할 수 없는 파일: ${rejected.join(", ")}`, "warning");
        if (accepted.length === 0) return;

        const totalCount = currentFileDetails.length + accepted.length;

        if (totalCount > effectiveMaxFileCount) {
          const allowedNewFiles = Math.max(0, effectiveMaxFileCount - currentFileDetails.length);
          const limitedFiles = accepted.slice(0, allowedNewFiles);
          setSelectedFiles(limitedFiles);
          onFilesChanged?.(limitedFiles);
          if (limitedFiles.length < accepted.length) {
            showToast(`최대 ${effectiveMaxFileCount}개까지만 업로드할 수 있습니다.`, "warning");
          }
        } else {
          setSelectedFiles(accepted);
          onFilesChanged?.(accepted);
        }
      },
      [
        currentFileDetails.length,
        effectiveMaxFileCount,
        onFilesChanged,
        maxFileSize,
        fileSettings.allowedFileExtensions,
      ],
    );

    const handleDeleteFile = useCallback((file: FileDetail) => {
      showMessage("삭제 확인", <div>파일을 삭제하시겠습니까?</div>, {
        type: "confirm",
        confirmText: "삭제",
        cancelText: "취소",
        callback: {
          onConfirm: async () => {
            setDeletingFiles((prev) => new Set(prev).add(file.file_sn));
            try {
              await deleteFile(file.atch_file_id, file.file_sn);
              showToast("파일이 삭제되었습니다.", "success");
              setCurrentFileDetails((prev) => prev.filter((f) => f.file_sn !== file.file_sn));
            } catch (error) {
              showToast(getApiErrorMessage(error), "error");
            } finally {
              setDeletingFiles((prev) => {
                const newSet = new Set(prev);
                newSet.delete(file.file_sn);
                return newSet;
              });
            }
          },
        },
      });
    }, []);

    const fieldPropsData = fieldName && getFieldProps ? getFieldProps(fieldName) : {};
    const isInvalid = fieldPropsData?.validationStatus === "invalid";

    return (
      <div className="w-full">
        {currentFileDetails.length > 0 && (
          <div className="mb-4">
            <div className="space-y-2">
              {currentFileDetails.map((file) => (
                <div key={file.file_sn} className="flex items-center justify-between p-2 bg-gray-50 rounded border">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="flex-shrink-0">
                      <FileTypeIcon extension={file.file_extsn || ""} fileName={file.orignl_file_nm || ""} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{file.orignl_file_nm}</div>
                      <div className="text-xs text-gray-500">{formatFileSize(file.file_mg || 0)}</div>
                    </div>
                  </div>
                  <Button
                    text="삭제"
                    onClick={() => handleDeleteFile(file)}
                    stylingMode="outlined"
                    type="danger"
                    width="auto"
                    height={28}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {isFinite(effectiveMaxFileCount) && (
          <div className="mb-2">
            <div className="text-sm font-medium text-gray-700">
              추가 업로드 ({currentFileDetails.length + selectedFiles.length}/{effectiveMaxFileCount})
              {fileSettings.allowedFileExtensions.length > 0 && (
                <span className="ml-2 text-[10px] text-gray-400">
                  (허용형식: {fileSettings.allowedFileExtensions.join(", ")})
                </span>
              )}
            </div>
          </div>
        )}

        {/* 드롭 존 — 클릭은 숨은 `<input type="file">` 을 연다. `<label>` 로 감싸므로 Tab 으로
            도달하고 Enter/Space 로 열린다(키보드 핸들러를 따로 달 필요가 없다). */}
        <label
          htmlFor={inputId}
          onDragOver={(e) => {
            if (!canAddMore) return;
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (canAddMore) handleFilesPicked(e.dataTransfer.files);
          }}
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded border border-dashed px-4 py-6 text-center",
            canAddMore
              ? "cursor-pointer border-gray-300 bg-white hover:bg-gray-50"
              : "cursor-not-allowed border-gray-200 bg-gray-50 opacity-60",
            isDragging ? "border-blue-500 bg-blue-50" : "",
            isInvalid ? "border-[#d9534f]" : "",
          )}
        >
          <Icon name="upload" size={24} className="text-gray-400" />
          <span className="text-sm text-gray-600">
            {canAddMore
              ? fileSettings.labelText
              : isFinite(effectiveMaxFileCount)
                ? `최대 ${effectiveMaxFileCount}개까지만 업로드할 수 있습니다.`
                : "최대 개수 도달"}
          </span>
          <span className="rounded border border-gray-300 bg-white px-3 py-1 text-sm">
            {canAddMore ? selectButtonText : "최대 개수 도달"}
          </span>
          <input
            id={inputId}
            ref={inputRef}
            type="file"
            multiple={multiple}
            accept={fileSettings.accept}
            disabled={!canAddMore}
            aria-invalid={isInvalid || undefined}
            className="sr-only"
            onChange={(e) => handleFilesPicked(e.target.files)}
          />
        </label>

        {/* 선택된(아직 업로드 전) 파일 목록 — 이관 전 위젯의 `showFileList` 자리다. */}
        {showFileListProp && selectedFiles.length > 0 && (
          <ul className="mt-2 space-y-1">
            {selectedFiles.map((file, index) => (
              <li key={`${file.name}-${index}`} className="flex items-center gap-2 rounded border bg-white px-2 py-1">
                <FileTypeIcon extension="" fileName={file.name} />
                <span className="min-w-0 flex-1 truncate text-sm text-gray-900">{file.name}</span>
                <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
                <button
                  type="button"
                  aria-label={`${file.name} 선택 해제`}
                  className="text-gray-400 hover:text-gray-600"
                  onClick={() => {
                    const updated = selectedFiles.filter((_, i) => i !== index);
                    setSelectedFiles(updated);
                    onFilesChanged?.(updated);
                    // 같은 파일을 다시 고를 수 있게 input 값을 비운다(브라우저는 값이 같으면
                    // change 를 안 쏜다).
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        {!isFinite(effectiveMaxFileCount) && fileSettings.allowedFileExtensions.length > 0 && (
          <div className="mt-1">
            <span className="text-xs text-gray-500">타입: {fileSettings.allowedFileExtensions.join(", ")}</span>
          </div>
        )}
      </div>
    );
  },
);

FileUploader.displayName = "FileUploader";
