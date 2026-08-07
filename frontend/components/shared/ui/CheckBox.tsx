// components/shared/ui/CheckBox.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";

interface Props<T = any> {
  fieldName: keyof T;
  value?: boolean;
  text?: string;
  readOnly?: boolean;
  iconSize?: number;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

/**
 * 체크박스 컴포넌트 (#341 ② — 네이티브 `<input type="checkbox">`)
 *
 * 동의/비동의, 선택/비선택 등 boolean 값 입력에 사용합니다.
 *
 * Radix `Checkbox` 를 쓰지 않는 이유: 네이티브 체크박스가 이미 폼 시맨틱·키보드(Space)·
 * 스크린리더 상태 전달을 전부 갖추고 있고, 이 화면들이 필요로 하는 커스텀 표시는 없다
 * (TextBox 가 Radix 없이 네이티브 `<input>` 을 쓰는 것과 같은 판단 — O8-3).
 *
 * `readOnly` 는 체크박스에 네이티브 대응이 없다(읽기 전용 체크박스는 값이 제출되지 않는
 * `disabled` 와 다르다). 그래서 `aria-readonly` 를 달고 변경만 막는다 — 포커스는 유지되어
 * 스크린리더 사용자가 값을 읽을 수 있다.
 *
 * @example
 * <CheckBox fieldName="isAgreed" text="개인정보 처리방침에 동의합니다" />
 */
export function CheckBox<T = any>({
  fieldName,
  value,
  text,
  readOnly = false,
  iconSize,
  onValueChanged,
  getFieldProps,
}: Props<T>) {
  const inputId = useId();
  const { isInvalid } = resolveFieldState(getFieldProps, fieldName);
  const boxSize = iconSize ? { width: iconSize, height: iconSize } : undefined;

  return (
    <span className="inline-flex items-center gap-2">
      <input
        id={inputId}
        type="checkbox"
        checked={value || false}
        aria-readonly={readOnly || undefined}
        aria-invalid={isInvalid || undefined}
        onChange={(e) => {
          if (readOnly) return;
          onValueChanged(fieldName, e.target.checked);
        }}
        style={boxSize}
        className={cn(
          "h-4 w-4 rounded border accent-blue-600",
          "focus:outline-none focus:ring-2 focus:ring-blue-500/40",
          readOnly ? "cursor-default" : "cursor-pointer",
          isInvalid ? "border-[#d9534f]" : "border-gray-300",
        )}
      />
      {text && (
        <label htmlFor={inputId} className={cn("text-sm text-gray-900", readOnly ? "" : "cursor-pointer")}>
          {text}
        </label>
      )}
    </span>
  );
}
