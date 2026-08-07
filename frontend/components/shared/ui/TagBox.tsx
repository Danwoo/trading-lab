// components/shared/ui/TagBox.tsx
"use client";

import { useId } from "react";
import { resolveFieldState } from "./primitives/fieldState";
import { FieldShell } from "./primitives/FieldShell";
import { SelectMenu } from "./primitives/SelectMenu";

interface Props<T = any> {
  fieldName: keyof T;
  value?: string[] | number[];
  items: any[];
  displayExpr?: string;
  valueExpr?: string;
  placeholder?: string;
  readOnly?: boolean;
  searchEnabled?: boolean;
  noDataText?: string;
  maxDisplayedTags?: number;
  showClearButton?: boolean;
  acceptCustomValue?: boolean;
  showSelectionControls?: boolean;
  width?: number | string;
  height?: number | string;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

/**
 * 다중 선택 태그 박스 (#341 ② — `SelectBox` 와 같은 `primitives/SelectMenu` 커널의 다중 모드)
 *
 * - 객체 배열: displayExpr(기본 "code_nm"), valueExpr(기본 "code") 사용
 * - 문자열 배열: displayExpr/valueExpr 무시하고 값 그대로 사용
 * - acceptCustomValue: 목록에 없는 값 직접 입력 허용
 *
 * 이관 전(DevExtreme)은 커스텀 값을 객체 배열에서 `{valueExpr, displayExpr}` 객체로 목록에
 * 얹었지만, 이 컴포넌트가 호출부에 돌려주는 것은 **언제나 값 배열**이었다(`onValueChanged` 가
 * `e.value` 를 그대로 넘겼다). 그래서 커널은 커스텀 값을 값 그대로 담는다 — 표시 이름은 목록에
 * 없으므로 값 자체가 라벨이 된다(문자열 배열일 때의 동작과 같다).
 */
export function TagBox<T = any>({
  fieldName,
  value = [],
  items,
  displayExpr = "code_nm",
  valueExpr = "code",
  placeholder = "선택하세요",
  readOnly = false,
  searchEnabled = true,
  noDataText,
  maxDisplayedTags,
  showClearButton,
  acceptCustomValue = false,
  showSelectionControls = false,
  width,
  height,
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
        multiple
        items={items}
        displayExpr={displayExpr}
        valueExpr={valueExpr}
        value={value}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        searchEnabled={searchEnabled}
        acceptCustomValue={acceptCustomValue}
        noDataText={noDataText}
        maxDisplayedTags={maxDisplayedTags}
        showClearButton={showClearButton}
        showSelectionControls={showSelectionControls}
        height={height}
        isInvalid={isInvalid}
        errorMessageId={errorMessageId}
        onChange={(next) => onValueChanged(fieldName, next)}
      />
    </FieldShell>
  );
}
