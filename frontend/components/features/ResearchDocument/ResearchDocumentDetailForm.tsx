"use client";

import { useRef } from "react";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, FileUploader, FileUploaderRef } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";

// 폼에서 편집하는 값은 doc_title 뿐 — 파일은 업로더가 보유(제출 시 합쳐 서비스로 전달)
interface ResearchDocumentFormData {
  doc_title?: string;
}

interface Props {
  isNew: boolean;
  initialData: Partial<ResearchDocumentFormData>;
  onSubmit: (data: ResearchDocumentFormData & { researchFiles?: File[] }) => Promise<boolean>;
  onCancel?: () => void;
}

export default function ResearchDocumentDetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } =
    useFormState<ResearchDocumentFormData>(initialData);

  const uploaderRef = useRef<FileUploaderRef>(null);

  // 폼 필드 + 업로더가 보유한 파일을 합쳐 서비스로 전달 (서비스가 업로드→atch_file_id·file_sn 치환)
  const handleFormSubmit = async (data: ResearchDocumentFormData) => {
    return await onSubmit({
      ...data,
      researchFiles: uploaderRef.current?.selectFiles() || [],
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="저장" onClick={() => handleSubmit(handleFormSubmit)} />
          {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="문서 제목" required colSpan={3}>
              <TextBox
                fieldName="doc_title"
                value={formData.doc_title}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          {/* 리서치 문서 파일 — 애널리스트 리포트·IR 덱·투자 메모(PDF/이미지/문서).
              문서 1건 = 파일 1개(색인 대상), 업로드 후 atch_file_id·file_sn 으로 치환 */}
          <TableRow>
            <TableCell label="문서 파일" required colSpan={3}>
              <FileUploader
                ref={uploaderRef}
                fileType="all"
                multiple={false}
                maxFileCount={1}
                fieldName="researchFiles"
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
