"use client";

import { useRef } from "react";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, NumberBox, TextArea, FileUploader, FileUploaderRef } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { Watchlist } from "@/schemas/watchlist/watchlist";

interface Props {
  isNew: boolean;
  initialData: Partial<Watchlist>;
  onSubmit: (data: Watchlist & { researchFiles?: File[] }) => Promise<boolean>;
  onCancel?: () => void;
  codeList?: any;
}

export default function WatchlistDetailForm({ initialData, isNew, codeList, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Watchlist>(initialData);

  const researchUploaderRef = useRef<FileUploaderRef>(null);

  // 폼 필드 + 업로더가 보유한 파일을 합쳐 서비스로 전달 (서비스가 업로드→atch_file_id 치환)
  const handleFormSubmit = async (data: Watchlist) => {
    return await onSubmit({
      ...data,
      researchFiles: researchUploaderRef.current?.selectFiles() || [],
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
            <TableCell label="티커" required>
              <TextBox
                fieldName="ticker"
                value={formData.ticker}
                readOnly={!isNew}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
            <TableCell label="종목명">
              <TextBox
                fieldName="issuer_nm"
                value={formData.issuer_nm}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="시장">
              <SelectBox
                fieldName="market"
                value={formData.market}
                items={codeList?.market}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
            <TableCell label="섹터">
              <SelectBox
                fieldName="sector"
                value={formData.sector}
                items={codeList?.sector}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="통화">
              <SelectBox
                fieldName="currency"
                value={formData.currency}
                items={codeList?.currency}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
            <TableCell label="우선순위">
              <SelectBox
                fieldName="priority"
                value={formData.priority}
                items={codeList?.priority}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="목표가">
              <NumberBox
                fieldName="target_price"
                value={formData.target_price}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
            <TableCell label="알림가">
              <NumberBox
                fieldName="alert_price"
                value={formData.alert_price}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="사용여부" required>
              <SelectBox
                fieldName="use_at"
                value={formData.use_at}
                items={codeList?.useAt}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="비고" colSpan={3}>
              <TextArea
                fieldName="memo"
                value={formData.memo}
                onValueChanged={handleFieldChange}
                getFieldProps={getFieldProps}
                maxLength={1300}
                height={100}
              />
            </TableCell>
          </TableRow>

          {/* 리서치 문서 첨부 — 애널리스트 리포트·IR 덱·투자 메모(PDF/이미지). 모델의 atch_file_id 1개에 대응하는 단일 슬롯 */}
          <TableRow>
            <TableCell label="리서치 문서" colSpan={3}>
              <FileUploader
                ref={researchUploaderRef}
                atchFileId={initialData.atch_file_id}
                fileType="all"
                multiple={true}
                maxFileCount={5}
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
