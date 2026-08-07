// components/shared/ui/DateRangeBox.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";

interface Props<T = any> {
  fieldName?: keyof T;
  value?: [Date | string | null, Date | string | null];
  placeholder?: string;
  readOnly?: boolean;
  type?: "date" | "datetime";
  /** 표시 형식은 브라우저 로케일이 정한다 — DateBox 와 같은 이유로 받아만 두고 무시한다. */
  displayFormat?: string;
  min?: Date | string | null;
  max?: Date | string | null;
  onValueChanged: (fieldName: keyof T | undefined, value: [string | null, string | null]) => void;
  getFieldProps?: (fieldName?: keyof T) => any;
}

/** 저장값(Date | ISO 문자열 | null) → 네이티브 입력이 읽는 로컬 벽시계 문자열 */
function toInputValue(raw: Date | string | null | undefined, type: "date" | "datetime"): string {
  if (!raw) return "";
  const date = raw instanceof Date ? raw : new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  return type === "datetime" ? `${day}T${pad(date.getHours())}:${pad(date.getMinutes())}` : day;
}

/** 네이티브 입력 문자열 → 호출부 계약(ISO 문자열 | null) */
function toIsoOrNull(inputValue: string): string | null {
  if (!inputValue) return null;
  const date = new Date(inputValue);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/**
 * 기간(시작~종료) 선택 컴포넌트 (#341 ② — 네이티브 날짜 입력 두 개)
 *
 * DevExtreme `DateRangeBox` 는 달력 하나에서 두 끝을 고르는 UI 였지만, 값 계약은 `[시작, 끝]`
 * ISO 문자열 쌍이라 네이티브 입력 두 개로 그대로 표현된다. 각 입력에 `aria-label` 을 달아
 * 스크린리더가 어느 쪽 끝인지 구분해 읽게 한다(시각적으로는 `~` 로만 구분되므로).
 *
 * 시작이 정해지면 끝의 `min` 을, 끝이 정해지면 시작의 `max` 를 그 값으로 좁혀 역전된 기간을
 * 브라우저 단에서 막는다.
 */
export function DateRangeBox<T = any>({
  fieldName,
  value = [null, null],
  placeholder: _placeholder,
  readOnly = false,
  type = "date",
  displayFormat: _displayFormat,
  min,
  max,
  onValueChanged,
  getFieldProps,
}: Props<T>) {
  const errorMessageId = useId();
  const { isInvalid, errorMessage, effectiveWidth } = resolveFieldState(getFieldProps, fieldName);

  const startValue = toInputValue(value[0], type);
  const endValue = toInputValue(value[1], type);
  const lowerBound = toInputValue(min ?? null, type) || undefined;
  const upperBound = toInputValue(max ?? null, type) || undefined;

  const emit = (nextStart: string, nextEnd: string) =>
    onValueChanged(fieldName, [toIsoOrNull(nextStart), toIsoOrNull(nextEnd)]);

  const inputClass = cn(FIELD_INPUT_CLASS, fieldBorderClass(isInvalid));
  const nativeType = type === "datetime" ? "datetime-local" : "date";

  return (
    <FieldShell
      isInvalid={isInvalid}
      errorMessage={errorMessage}
      errorMessageId={errorMessageId}
      width={effectiveWidth ?? (type === "date" ? "250px" : undefined)}
      className="flex w-full items-center gap-1"
    >
      <input
        type={nativeType}
        aria-label="시작일"
        value={startValue}
        readOnly={readOnly}
        min={lowerBound}
        max={endValue || upperBound}
        onChange={(e) => emit(e.target.value, endValue)}
        aria-invalid={isInvalid || undefined}
        aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
        className={inputClass}
      />
      <span aria-hidden="true" className="shrink-0 text-sm text-gray-500">
        ~
      </span>
      <input
        type={nativeType}
        aria-label="종료일"
        value={endValue}
        readOnly={readOnly}
        min={startValue || lowerBound}
        max={upperBound}
        onChange={(e) => emit(startValue, e.target.value)}
        aria-invalid={isInvalid || undefined}
        className={inputClass}
      />
    </FieldShell>
  );
}
