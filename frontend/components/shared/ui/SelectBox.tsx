// components/shared/ui/SelectBox.tsx
"use client";

import React, { useId } from "react";
import { resolveFieldState } from "./primitives/fieldState";
import { FieldShell } from "./primitives/FieldShell";
import { SelectMenu } from "./primitives/SelectMenu";

interface Props<T = any> {
  fieldName: keyof T;
  value?: string | number | null;
  items: any[];
  displayExpr?: string;
  valueExpr?: string;
  placeholder?: string;
  readOnly?: boolean;
  searchEnabled?: boolean;
  noDataText?: string;
  showClearButton?: boolean;
  acceptCustomValue?: boolean;
  width?: number | string;
  height?: number | string;
  disabled?: boolean;
  itemRender?: (item: any) => React.ReactNode;
  fieldRender?: (item: any) => React.ReactNode;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

/**
 * 단일 선택 드롭다운 (#341 ② — Radix Popover 기반 `primitives/SelectMenu`)
 *
 * - 객체 배열: displayExpr(기본 "code_nm"), valueExpr(기본 "code") 사용
 * - 문자열 배열: displayExpr/valueExpr 무시하고 값 그대로 사용
 * - acceptCustomValue: 목록에 없는 값 직접 입력 허용
 */
export function SelectBox<T = any>({
  fieldName,
  value,
  items,
  displayExpr = "code_nm",
  valueExpr = "code",
  placeholder = "-- 선택 --",
  readOnly = false,
  searchEnabled = false,
  noDataText,
  showClearButton,
  acceptCustomValue = false,
  width,
  height,
  disabled,
  itemRender,
  fieldRender,
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
      <SelectMenu
        items={items}
        displayExpr={displayExpr}
        valueExpr={valueExpr}
        value={value === "" ? null : (value ?? null)}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        disabled={disabled}
        searchEnabled={searchEnabled || acceptCustomValue}
        acceptCustomValue={acceptCustomValue}
        noDataText={noDataText}
        showClearButton={showClearButton}
        height={height}
        itemRender={itemRender}
        fieldRender={fieldRender}
        isInvalid={isInvalid}
        errorMessageId={errorMessageId}
        onChange={(next) => onValueChanged(fieldName, next)}
      />
    </FieldShell>
  );
}
