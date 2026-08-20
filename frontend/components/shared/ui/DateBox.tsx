// components/shared/ui/DateBox.tsx
"use client";

import { useEffect, useId, useRef, useState } from "react";
import { cn } from "./primitives/cn";
import { resolveFieldState } from "./primitives/fieldState";
import { FIELD_ICON_BUTTON_CLASS, FIELD_INPUT_CLASS, FieldShell, fieldBorderClass } from "./primitives/FieldShell";
import { Icon } from "./primitives/icons";

interface Props<T = any> {
  fieldName: keyof T;
  value?: string; // YYYY-MM-DD 형식
  placeholder?: string;
  readOnly?: boolean;
  type?: "date" | "datetime" | "time";
  /**
   * 표시 형식. `date` 모드의 표기는 값 계약과 같은 `YYYY-MM-DD` 로 고정이고, `datetime`·`time`
   * 은 네이티브 입력이라 표시 형식을 브라우저가 정한다 — 어느 쪽도 여기서 못 바꾸므로 받아만
   * 두고 무시한다.
   */
  displayFormat?: string;
  min?: Date | string;
  max?: Date | string;
  onValueChanged: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
}

const NATIVE_INPUT_TYPE = { date: "date", datetime: "datetime-local", time: "time" } as const;

/** 값 계약 형식이자 `date` 모드의 표시 형식. */
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** 달력에 없는 날(2026-02-31)을 값으로 올리지 않는다 — 자릿수만 맞으면 정규식은 통과한다. */
function isRealDate(iso: string): boolean {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

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
 * 날짜 선택 컴포넌트 (#341 ②)
 *
 * 값 계약: `date` → `YYYY-MM-DD`, `datetime` → ISO 문자열, `time` → `HH:mm:ss`, 비우면 `null`.
 *
 * **`date` 모드는 네이티브 `<input type="date">` 를 화면에 세우지 않는다** (#282). 네이티브
 * 날짜 입력의 표시 형식은 브라우저·OS 로케일이 정해서 앱이 못 정한다 — 같은 화면의 다른 날짜가
 * `2026-08-19` 인데 폼만 `08/21/2023` 으로 말하는 상태가 그래서 생겼다. 값 계약이 이미
 * `YYYY-MM-DD` 이므로, 그 문자열을 그대로 보이는 텍스트 입력이 표기와 계약을 한 형식으로 묶는다.
 *
 * 달력은 버리지 않는다 — 숨은 네이티브 날짜 입력을 옆에 두고 「달력」 버튼이 `showPicker()` 로
 * 연다. `showPicker()` 가 없는 브라우저에서는 버튼을 아예 그리지 않는다(죽은 버튼을 남기지
 * 않는다). `datetime`·`time` 은 이 이슈의 대상이 아니라 네이티브 입력 그대로다.
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
  const pickerRef = useRef<HTMLInputElement>(null);
  const [canOpenPicker, setCanOpenPicker] = useState(false);
  // 타이핑 중인 원문. 완성된 날짜가 되기 전의 `2023-0` 를 값으로 올리면 계약이 깨지므로
  // 화면에만 두고, 포커스를 잃으면 버려 마지막 성한 값으로 되돌린다.
  const [draft, setDraft] = useState<string | null>(null);

  useEffect(() => {
    setCanOpenPicker(typeof HTMLInputElement.prototype.showPicker === "function");
  }, []);

  const handleNativeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (!raw) {
      onValueChanged(fieldName, null);
      return;
    }
    // `datetime` 만 ISO 로 올린다 — date/time 은 입력 문자열이 곧 계약 형식이다.
    onValueChanged(fieldName, type === "datetime" ? new Date(raw).toISOString() : raw);
  };

  if (type === "date") {
    const showPickerButton = canOpenPicker && !readOnly;
    // ISO 날짜는 사전순 비교가 곧 시간순 비교다 — 네이티브 입력이 대신 막아 주던 min/max 를
    // 텍스트 입력에서도 같은 자리에 세운다.
    const lower = toInputBound(min, type);
    const upper = toInputBound(max, type);
    const withinBounds = (iso: string) => (!lower || iso >= lower) && (!upper || iso <= upper);
    return (
      <FieldShell
        isInvalid={isInvalid}
        errorMessage={errorMessage}
        errorMessageId={errorMessageId}
        width={effectiveWidth}
      >
        <input
          type="text"
          inputMode="numeric"
          value={draft ?? value ?? ""}
          placeholder={readOnly ? "" : (placeholder ?? "YYYY-MM-DD")}
          readOnly={readOnly}
          onChange={(e) => {
            const raw = e.target.value;
            setDraft(raw);
            if (raw === "") onValueChanged(fieldName, null);
            else if (ISO_DATE.test(raw) && isRealDate(raw) && withinBounds(raw)) onValueChanged(fieldName, raw);
          }}
          onBlur={() => setDraft(null)}
          aria-invalid={isInvalid || undefined}
          aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
          className={cn(FIELD_INPUT_CLASS, fieldBorderClass(isInvalid), showPickerButton ? "pr-9" : "")}
        />
        {showPickerButton && (
          <>
            <button
              type="button"
              aria-label="달력에서 고르기"
              onClick={() => pickerRef.current?.showPicker()}
              onMouseDown={(e) => e.preventDefault()}
              className={FIELD_ICON_BUTTON_CLASS}
            >
              <Icon name="event" size={18} />
            </button>
            {/* 달력 팝업의 앵커. `display:none` 이면 showPicker() 가 InvalidStateError 를 던지므로
                크기 0 + 투명으로 세워 두고, 탭 순서와 접근성 트리에서만 뺀다. */}
            <input
              ref={pickerRef}
              type="date"
              tabIndex={-1}
              aria-hidden="true"
              value={value ?? ""}
              min={lower}
              max={upper}
              onChange={(e) => {
                setDraft(null);
                onValueChanged(fieldName, e.target.value || null);
              }}
              className="pointer-events-none absolute bottom-0 right-2 h-px w-px opacity-0"
            />
          </>
        )}
      </FieldShell>
    );
  }

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
        onChange={handleNativeChange}
        aria-invalid={isInvalid || undefined}
        aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
        className={cn(FIELD_INPUT_CLASS, fieldBorderClass(isInvalid))}
      />
    </FieldShell>
  );
}
