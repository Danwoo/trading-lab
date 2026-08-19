// components/shared/ui/NumberBox.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";

interface Props<T = any> {
  /** 바깥 라벨(`<label htmlFor>`)과 잇는 id. 안 주면 라벨과 안 이어진다. */
  id?: string;
  /** 도움말 문단과 잇는 id — 검증 오류가 있을 때는 그쪽이 이긴다. */
  "aria-describedby"?: string;
  fieldName: keyof T;
  value?: number | null;
  placeholder?: string;
  readOnly?: boolean;
  min?: number;
  max?: number;
  step?: number; // 증감 단위 (기본: 1)
  /**
   * 표시 형식. DevExtreme 시절의 `#,##0원` 같은 패턴 문자열을 그대로 받되, 여기서는
   * **접미사(suffix)만** 해석한다 — 자릿수 구분(`#,##0`)은 항상 적용하고 그 뒤에 붙은 리터럴을
   * 단위로 붙인다. 실사용 전수(#341 ②)에서 쓰이는 형태가 `#,##0` 계열 + 단위뿐이었다.
   */
  format?: string;
  showSpinButtons?: boolean;
  visible?: boolean; // 컴포넌트 표시 여부
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
  width?: number | string;
  height?: number | string;
  disabled?: boolean;
  tabIndex?: number;
}

/** `#,##0원` → `원` (자릿수 패턴 뒤에 남은 리터럴만 단위로 본다) */
function suffixOf(format?: string): string {
  if (!format) return "";
  return format.replace(/[#0,.]/g, "");
}

/**
 * 숫자 입력 컴포넌트 (#341 ② — 네이티브 `<input type="number">`)
 *
 * 나이, 연봉, 수량, 금액 등 숫자 값 입력에 사용합니다.
 *
 * `type="number"` 는 브라우저가 증감 버튼·숫자 키패드·검증을 이미 갖고 있어 그대로 쓴다.
 * `showSpinButtons=false` 면 CSS 로 그 버튼만 감춘다(`[appearance:textfield]`) — 값 계약과
 * 키보드 ↑↓ 동작은 그대로 남는다.
 *
 * 읽기 전용일 때는 단위(`format` 접미사)를 값 옆에 덧붙여 보여준다 — 편집 중에는 숨긴다
 * (네이티브 숫자 입력은 리터럴을 값으로 받지 못한다).
 *
 * @example
 * <NumberBox fieldName="salary" min={0} format="#,##0원" showSpinButtons />
 */
export function NumberBox<T = any>({
  fieldName,
  value,
  placeholder,
  readOnly = false,
  min,
  max,
  step = 1,
  format,
  showSpinButtons = false,
  visible = true,
  onValueChanged,
  getFieldProps,
  id,
  "aria-describedby": describedBy,
  width,
  height,
  disabled,
  tabIndex,
}: Props<T>) {
  const errorMessageId = useId();
  const { isInvalid, errorMessage, effectiveWidth } = resolveFieldState(getFieldProps, fieldName, width);

  if (!visible) return null;

  const suffix = suffixOf(format);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    // 빈 문자열은 0 이 아니라 "값 없음"이다 — DevExtreme 도 null 을 넘겼다.
    onValueChanged(fieldName, raw === "" ? null : Number(raw));
  };

  return (
    <FieldShell
      isInvalid={isInvalid}
      errorMessage={errorMessage}
      errorMessageId={errorMessageId}
      width={effectiveWidth}
    >
      <input
        type="number"
        id={id}
        value={value ?? ""}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        disabled={disabled}
        tabIndex={tabIndex}
        min={min}
        max={max}
        step={step}
        onChange={handleChange}
        aria-invalid={isInvalid || undefined}
        // 검증 오류가 있으면 그쪽이 이긴다 — 지금 고쳐야 할 것이 먼저 읽혀야 한다.
        aria-describedby={isInvalid && errorMessage ? errorMessageId : describedBy}
        style={{ height }}
        className={cn(
          FIELD_INPUT_CLASS,
          "text-right",
          fieldBorderClass(isInvalid),
          // 스핀 버튼을 끄면 WebKit/Firefox 양쪽에서 감춘다(값·키보드 동작은 유지).
          showSpinButtons
            ? ""
            : "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
          readOnly && suffix ? "pr-8" : "",
        )}
      />
      {readOnly && suffix && (
        <span aria-hidden="true" className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">
          {suffix}
        </span>
      )}
    </FieldShell>
  );
}
