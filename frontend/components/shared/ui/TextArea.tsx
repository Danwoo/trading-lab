// components/shared/ui/TextArea.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";

interface Props<T = any> {
  /** 바깥에 보이는 라벨이 없을 때의 이름. placeholder 는 이름이 아니다. */
  "aria-label"?: string;
  /** 바깥 라벨(`<label htmlFor>`)과 잇는 id. 안 주면 라벨과 안 이어진다. */
  id?: string;
  /** 도움말 문단과 잇는 id — 검증 오류가 있을 때는 그쪽이 이긴다. */
  "aria-describedby"?: string;
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
  id,
  "aria-describedby": describedBy,
  "aria-label": ariaLabel,
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
        id={id}
        aria-label={ariaLabel}
        value={value || ""}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        maxLength={maxLength}
        onChange={(e) => onValueChanged(fieldName, e.target.value)}
        aria-invalid={isInvalid || undefined}
        // 검증 오류가 있으면 그쪽이 이긴다 — 지금 고쳐야 할 것이 먼저 읽혀야 한다.
        aria-describedby={isInvalid && errorMessage ? errorMessageId : describedBy}
        style={{ height }}
        className={cn(FIELD_INPUT_CLASS, "block resize-y leading-normal", fieldBorderClass(isInvalid))}
      />
    </FieldShell>
  );
}
