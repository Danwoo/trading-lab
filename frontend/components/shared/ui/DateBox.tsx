// components/shared/ui/DateBox.tsx
"use client";

import { useId } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";

interface Props<T = any> {
  fieldName: keyof T;
  value?: string; // YYYY-MM-DD 형식
  placeholder?: string;
  readOnly?: boolean;
  type?: "date" | "datetime" | "time";
  /**
   * 표시 형식. 네이티브 날짜 입력은 표시 형식을 **브라우저 로케일**이 정하므로 여기서 강제할 수
   * 없다 — 받아만 두고 무시한다(값 계약은 `type` 이 정한다). 형식을 반드시 통제해야 하는 화면이
   * 생기면 그때 텍스트 입력 + 파서로 확장한다.
   */
  displayFormat?: string;
  min?: Date | string;
  max?: Date | string;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

const NATIVE_INPUT_TYPE = { date: "date", datetime: "datetime-local", time: "time" } as const;

/** `min`/`max` 를 네이티브 입력이 받는 문자열로 — Date 든 문자열이든 같은 자리로 모은다. */
function toInputBound(bound: Date | string | undefined, type: Props["type"]): string | undefined {
  if (bound === undefined || bound === null) return undefined;
  const date = bound instanceof Date ? bound : new Date(bound);
  if (Number.isNaN(date.getTime())) return undefined;
  if (type === "time") return date.toTimeString().slice(0, 5);
  const iso = toLocalIso(date);
  return type === "datetime" ? iso.slice(0, 16) : iso.slice(0, 10);
}

/**
 * 로컬 시간대 기준 ISO 문자열. `toISOString()` 은 UTC 로 옮기므로 KST(+9)에서는 날짜가 하루
 * 밀린다 — 네이티브 date 입력이 다루는 것은 **벽시계 날짜**라 로컬 기준으로 만들어야 한다.
 */
function toLocalIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

/**
 * 날짜 선택 컴포넌트 (#341 ② — 네이티브 `<input type="date|datetime-local|time">`)
 *
 * 브라우저 기본 달력 UI 를 그대로 쓴다 — 키보드 입력·달력 팝업·스크린리더 지원이 이미 갖춰져
 * 있고, 자체 달력을 만들면 그 셋을 전부 다시 구현해야 한다.
 *
 * 값 계약은 이관 전과 같다: `date` → `YYYY-MM-DD`, `datetime` → ISO 문자열, `time` → `HH:mm:ss`,
 * 비우면 `null`.
 *
 * @example
 * <DateBox fieldName="birthDate" type="datetime" />
 */
export function DateBox<T = any>({
  fieldName,
  value,
  placeholder,
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (!raw) {
      onValueChanged(fieldName, null);
      return;
    }
    // `datetime` 만 ISO 로 올린다 — date/time 은 입력 문자열이 곧 계약 형식이다.
    onValueChanged(fieldName, type === "datetime" ? new Date(raw).toISOString() : raw);
  };

  // 저장된 값 → 네이티브 입력이 읽는 형태. datetime 은 ISO(UTC)로 저장되므로 로컬로 되돌린다.
  const inputValue = (() => {
    if (!value) return "";
    if (type === "datetime") {
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? "" : toLocalIso(date).slice(0, 16);
    }
    return value;
  })();

  return (
    <FieldShell
      isInvalid={isInvalid}
      errorMessage={errorMessage}
      errorMessageId={errorMessageId}
      width={effectiveWidth}
    >
      <input
        type={NATIVE_INPUT_TYPE[type]}
        value={inputValue}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        min={toInputBound(min, type)}
        max={toInputBound(max, type)}
        onChange={handleChange}
        aria-invalid={isInvalid || undefined}
        aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
        className={cn(FIELD_INPUT_CLASS, fieldBorderClass(isInvalid))}
      />
    </FieldShell>
  );
}
