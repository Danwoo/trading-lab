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
 * 선언한 범위를 값이 벗어난 상태를 글로 말한다 (#398).
 *
 * `min`/`max` 는 네이티브 입력에 그대로 실려 **브라우저의 제출 차단**이 된다. 그런데 그 차단은
 * 잘못된 칸에 포커스를 줄 수 있을 때만 말풍선을 띄운다 — 이 레포의 폼 상당수가 넓은·좁은 배치에
 * 두 벌 마운트되어 한 벌이 `display:none` 이라(§21.6), 안 보이는 쪽이 걸리면 **아무 말 없이
 * 버튼만 죽는다**. 실측(#398): 칸 수에 `99` 를 넣으면 폼은 `495칸` 을 약속하는데 실행을 눌러도
 * 요청 0건·콘솔 0건·글자 변화 0건이었다.
 *
 * 그래서 범위를 선언한 칸은 벗어난 값을 **그 자리에서** 말한다. 값을 대신 눌러 주지는 않는다 —
 * `5~120` 같은 넓은 범위에서 한 글자씩 누르면 `12` 를 칠 수 없다. 눌러야 하는 칸(칸 수처럼
 * 범위가 한 자리인 곳)은 상태를 가진 쪽이 누른다.
 */
function outOfRangeMessage(value: number | null | undefined, min?: number, max?: number): string | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  if (min !== undefined && max !== undefined && (value < min || value > max))
    return `${min}~${max} 사이로 적으세요.`;
  if (min !== undefined && value < min) return `${min} 이상으로 적으세요.`;
  if (max !== undefined && value > max) return `${max} 이하로 적으세요.`;
  return undefined;
}

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
 * **단위(`format` 접미사)는 읽기 전용이든 편집 중이든 언제나 보인다 (#316).** 값이 비어 있어도
 * 보이므로, 칸을 처음 보는 사람도 무엇을 치는 자리인지 안다. 단위는 값이 아니라 **입력 옆에
 * 겹쳐 그리는 글자**다 — 네이티브 숫자 입력은 리터럴을 값으로 받지 못하므로 값에 섞을 수 없다.
 * 그래서 겹치지 않게 입력의 오른쪽 여백을 단위 길이만큼 벌리고, 그 글자를 `aria-describedby`
 * 로 이어 보조기술도 함께 읽게 한다. `groupDigits` 모드는 값 자체가 `10,000,000원` 이라
 * 여기서 덧붙이지 않는다.
 *
 * `showSpinButtons` 와 단위는 같은 자리(입력의 오른쪽 끝)를 다투므로 함께 켜지 않는다.
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
  const suffixId = useId();
  const { isInvalid, errorMessage, effectiveWidth } = resolveFieldState(getFieldProps, fieldName, width);
  // 편집 중인 원문. 구분 기호를 넣은 표기 위에 커서를 올리면 자릿수가 밀리므로, 편집하는 동안은
  // 이 원문을 그대로 보여 준다.
  const [draft, setDraft] = useState<string | null>(null);
  // 친 글자를 숫자로 못 읽었다는 사실. 값은 비우되 화면에는 친 글자를 남겨 사유와 함께 보인다.
  const [unreadable, setUnreadable] = useState(false);

  if (!visible) return null;

  const suffix = suffixOf(format);
  const editing = draft !== null;
  // `groupDigits` 는 값 문자열에 단위를 이미 담는다 — 여기서 또 그리면 `10,000,000원원` 이 된다.
  const showsSuffix = suffix !== "" && !groupDigits;

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

  // 범위 밖 판정은 네이티브 `min`/`max` 가 실제로 입력에 실리는 갈래에서만 한다 — `groupDigits`
  // 는 그 둘을 떼고 텍스트 입력이 되므로 브라우저가 막지 않고, 여기서만 빨개지면 거짓 경보다.
  const rangeError = groupDigits ? undefined : outOfRangeMessage(value, min, max);
  const shownError = isInvalid ? errorMessage : unreadable ? UNREADABLE_MESSAGE : rangeError;
  const showsError = isInvalid || unreadable || rangeError !== undefined;
  const describedByIds =
    [showsError && shownError ? errorMessageId : describedBy, showsSuffix ? suffixId : undefined]
      .filter(Boolean)
      .join(" ") || undefined;

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
        // 검증 오류가 있으면 도움말 대신 그쪽이 읽힌다 — 지금 고쳐야 할 것이 먼저다. 단위는
        // 어느 쪽이든 뒤에 붙는다(무엇을 치는 자리인지는 오류 중에도 알아야 한다).
        aria-describedby={describedByIds}
        // 단위 글자와 값이 겹치지 않게 오른쪽만 벌린다 — `px-3`(0.75rem) 의 오른쪽을 덮어쓴다.
        style={{ height, paddingRight: showsSuffix ? `calc(0.75rem + ${suffix.length}em)` : undefined }}
        className={cn(
          FIELD_INPUT_CLASS,
          "text-right tabular-nums",
          fieldBorderClass(showsError),
          // 스핀 버튼을 끄면 WebKit/Firefox 양쪽에서 감춘다(값·키보드 동작은 유지).
          showSpinButtons
            ? ""
            : "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
        )}
      />
      {showsSuffix && (
        // 클릭이 통과해야 오른쪽 끝을 눌러도 칸에 포커스가 간다.
        <span
          id={suffixId}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted"
        >
          {suffix}
        </span>
      )}
    </FieldShell>
  );
}
