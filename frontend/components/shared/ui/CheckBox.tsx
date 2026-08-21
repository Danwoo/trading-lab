// components/shared/ui/CheckBox.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";

interface Props<T = any> {
  /** 바깥 라벨(`<label htmlFor>`)이 가리킬 id. 안 주면 스스로 만든다. */
  id?: string;
  "aria-describedby"?: string;
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
  id,
  "aria-describedby": describedBy,
}: Props<T>) {
  // 바깥에서 라벨을 세웠으면 그 id 를 쓴다 — 자기 id 를 고집하면 라벨이 딴 곳을 가리킨다.
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const { isInvalid } = resolveFieldState(getFieldProps, fieldName);
  const boxSize = iconSize ? { width: iconSize, height: iconSize } : undefined;

  return (
    <span className="inline-flex items-center gap-2">
      <input
        id={inputId}
        aria-describedby={describedBy}
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
          // 체크색은 네이티브 기본에 맡긴다 — 셸이 `color-scheme` 을 선언하므로 브라우저가
          // 테마에 맞춰 고른다. 팔레트 색을 박으면 반대 테마에서 어긋나고 accent 토큰은 없다.
          // 포커스 표시는 globals.css 의 `:focus-visible` outline 한 자리가 정본이다 —
          // `focus:outline-none` 을 얹으면 명시도로 그것을 덮어 표시를 지운다.
          "h-4 w-4 rounded border",
          readOnly ? "cursor-default" : "cursor-pointer",
          isInvalid ? "border-danger" : "border-line",
        )}
      />
      {/* 라벨은 잉크 토큰 — gray-900 은 다크 패널 위에서 1.01:1 로 글자가 사라진다 (#203 실측). */}
      {text && (
        <label htmlFor={inputId} className={cn("text-sm text-ink", readOnly ? "" : "cursor-pointer")}>
          {text}
        </label>
      )}
    </span>
  );
}
