// components/shared/ui/TextArea.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";

interface Props<T = any> {
  fieldName: keyof T;
  value?: string;
  placeholder?: string;
  readOnly?: boolean;
  width?: number | string;
  height?: number | string; // 텍스트 영역 높이 (px 또는 "100%" 등 — flex 채우기 시)
  maxLength?: number;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

/**
 * 다중 라인 텍스트 입력 컴포넌트 (#341 ② — 네이티브 `<textarea>`)
 *
 * 비고, 설명, 메모 등 긴 텍스트 입력에 사용합니다.
 *
 * @example
 * <TextArea fieldName="memo" height={120} maxLength={500} placeholder="메모 (최대 500자)" />
 */
export function TextArea<T = any>({
  fieldName,
  value,
  placeholder,
  readOnly = false,
  width,
  height = 80,
  maxLength,
  onValueChanged,
  getFieldProps,
}: Props<T>) {
  const errorMessageId = useId();
  const { isInvalid, errorMessage, effectiveWidth } = resolveFieldState(getFieldProps, fieldName, width);

  return (
    <FieldShell
      isInvalid={isInvalid}
      errorMessage={errorMessage}
      errorMessageId={errorMessageId}
      width={effectiveWidth}
    >
      <textarea
        value={value || ""}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        maxLength={maxLength}
        onChange={(e) => onValueChanged(fieldName, e.target.value)}
        aria-invalid={isInvalid || undefined}
        aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
        style={{ height }}
        className={cn(FIELD_INPUT_CLASS, "block resize-y leading-normal", fieldBorderClass(isInvalid))}
      />
    </FieldShell>
  );
}
