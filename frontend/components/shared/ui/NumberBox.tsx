// components/shared/ui/NumberBox.tsx
"use client";

import { useId, useState } from "react";
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
   * **접미사(suffix)만** 해석한다 — 자릿수 구분은 `groupDigits` 가 켜졌을 때만 붙는다.
   * 실사용 전수(#341 ②)에서 쓰이는 형태가 `#,##0` 계열 + 단위뿐이었다.
   */
  format?: string;
  /**
   * 천단위 구분(`10,000,000`)을 보인다. 켜면 네이티브 숫자 입력 대신 텍스트 입력이 된다 —
   * `type="number"` 는 쉼표가 섞인 문자열을 값으로 받지 못해 칸이 빈 것처럼 보인다. 대신
   * 스핀 버튼·`min`/`max`/`step` 같은 네이티브 숫자 기능은 이 모드에서 붙지 않는다.
   * 편집 중에는 구분 없는 원본 숫자를 보여 타이핑을 방해하지 않고, 포커스를 잃으면 다시 묶는다.
   */
  groupDigits?: boolean;
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
 * 리포트 화면(`RunReportView`)이 쓰는 것과 같은 규칙 — 같은 값을 입력에서와 출력에서 다르게
 * 읽으면 안 된다. 소수 자릿수는 자르지 않는다(기본값 3 은 값을 조용히 반올림한다).
 */
function groupDigitsOf(value: number): string {
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 20 });
}

/** 구분 기호와 단위를 벗긴 뒤 남아야 하는 십진 표기. */
const DECIMAL_TEXT = /^[+-]?(\d+(\.\d*)?|\.\d+)$/;

/**
 * 화면에 보이는 표기(`10,000,000원`)를 그대로 되쳐도 같은 값으로 읽는다 — 칸이 평상시에 그
 * 형식을 보이는 이상 그렇게 치는 것은 예외 입력이 아니다. 구분 기호와 단위를 벗기고 읽는다.
 *
 * `Number()` 를 그대로 믿지 않는 이유: `1e9`·`0x10`·`Infinity`·공백까지 숫자가 된다.
 * `Infinity` 는 `∞원` 으로 그려지고 JSON 직렬화에서 `null` 이 되어 요청 본문이 계약을 깬다.
 */
function parseAmount(raw: string, suffix: string): number | null {
  let text = raw.trim();
  if (suffix && text.endsWith(suffix)) text = text.slice(0, -suffix.length).trim();
  text = text.replace(/,/g, "");
  if (!DECIMAL_TEXT.test(text)) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

/** 못 읽은 글자를 옛 값 위에 조용히 남기지 않으려면, 사유를 이 자리에서 말해야 한다. */
const UNREADABLE_MESSAGE = "숫자로 읽을 수 없습니다 — 숫자와 쉼표로 적으세요.";

/**
 * 숫자 입력 컴포넌트 (#341 ② — 네이티브 `<input type="number">`)
 *
 * 나이, 연봉, 수량, 금액 등 숫자 값 입력에 사용합니다. 금액처럼 자릿수를 읽어야 하는 칸은
 * `groupDigits` 로 천단위 구분을 켠다 (#283).
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
  groupDigits = false,
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
  // 편집 중인 원문. 구분 기호를 넣은 표기 위에 커서를 올리면 자릿수가 밀리므로, 편집하는 동안은
  // 이 원문을 그대로 보여 준다.
  const [draft, setDraft] = useState<string | null>(null);
  // 친 글자를 숫자로 못 읽었다는 사실. 값은 비우되 화면에는 친 글자를 남겨 사유와 함께 보인다.
  const [unreadable, setUnreadable] = useState(false);

  if (!visible) return null;

  const suffix = suffixOf(format);
  const editing = draft !== null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (!groupDigits) {
      // 네이티브 숫자 입력은 못 읽는 글자를 빈 문자열로 준다 — 여기 오는 것은 숫자거나 빔이다.
      onValueChanged(fieldName, raw === "" ? null : Number(raw));
      return;
    }
    setDraft(raw);
    // 빈 문자열은 0 이 아니라 "값 없음"이다 — DevExtreme 도 null 을 넘겼다.
    if (raw.trim() === "") {
      setUnreadable(false);
      onValueChanged(fieldName, null);
      return;
    }
    const parsed = parseAmount(raw, suffix);
    setUnreadable(parsed === null);
    // 못 읽으면 옛 값을 지키지 않고 비운다 — 화면과 올라간 값이 어긋난 채 제출되는 길을 막는다
    // (텍스트 칸에서 Enter 를 치면 블러 없이 폼이 제출된다).
    onValueChanged(fieldName, parsed);
  };

  const shownError = isInvalid ? errorMessage : unreadable ? UNREADABLE_MESSAGE : undefined;
  const showsError = isInvalid || unreadable;

  const displayValue = groupDigits
    ? editing
      ? draft
      : value === null || value === undefined
        ? ""
        : `${groupDigitsOf(value)}${suffix}`
    : (value ?? "");

  return (
    <FieldShell isInvalid={showsError} errorMessage={shownError} errorMessageId={errorMessageId} width={effectiveWidth}>
      <input
        type={groupDigits ? "text" : "number"}
        inputMode={groupDigits ? "decimal" : undefined}
        id={id}
        value={displayValue}
        placeholder={readOnly ? "" : placeholder}
        readOnly={readOnly}
        disabled={disabled}
        tabIndex={tabIndex}
        min={groupDigits ? undefined : min}
        max={groupDigits ? undefined : max}
        step={groupDigits ? undefined : step}
        // 못 읽은 글자가 남아 있으면 그대로 두고 고치게 한다 — 지우면 무엇이 틀렸는지 사라진다.
        onFocus={
          groupDigits
            ? () => setDraft((prev) => prev ?? (value === null || value === undefined ? "" : String(value)))
            : undefined
        }
        // 못 읽은 글자는 버리지 않는다 — 조용히 옛 값으로 되돌아가면 기각된 사실이 안 보인다.
        onBlur={
          groupDigits
            ? () => {
                if (!unreadable) setDraft(null);
              }
            : undefined
        }
        onChange={handleChange}
        aria-invalid={showsError || undefined}
        // 검증 오류가 있으면 그쪽이 이긴다 — 지금 고쳐야 할 것이 먼저 읽혀야 한다.
        aria-describedby={showsError && shownError ? errorMessageId : describedBy}
        style={{ height }}
        className={cn(
          FIELD_INPUT_CLASS,
          "text-right tabular-nums",
          fieldBorderClass(showsError),
          // 스핀 버튼을 끄면 WebKit/Firefox 양쪽에서 감춘다(값·키보드 동작은 유지).
          showSpinButtons
            ? ""
            : "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
          readOnly && suffix && !groupDigits ? "pr-8" : "",
        )}
      />
      {readOnly && suffix && !groupDigits && (
        <span aria-hidden="true" className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted">
          {suffix}
        </span>
      )}
    </FieldShell>
  );
}
