// components/shared/ui/TextBox.tsx
"use client";

import { useId, useState } from "react";
import { cn } from "./primitives/cn";
import { Icon } from "./primitives/icons";

/**
 * 클리어·비밀번호 토글 아이콘의 클래스.
 *
 * **어두운 셸과 흰 `/admin` 양쪽에서 읽히는 색 하나**를 쓴다. 종전에는 `text-gray-400/500` 에
 * `hover:text-gray-600/700` 이었는데, hover 색이 밝은 바탕 전제라 어두운 셸에서는 **대비가
 * 1.57:1 로 떨어져 마우스를 올리면 아이콘이 사라졌다**.
 *
 * 왜 토큰(`text-ink-*`)이 아닌가: `:root` 가 다크 기본이고 `/admin` 셸은 `bg-white` 인데
 * `data-theme="light"` 가 없다 — 토큰을 쓰면 흰 바탕에 다크 잉크가 얹혀 안 보인다.
 * 왜 `text-current` 도 아닌가: 이 래퍼에는 잉크가 없어 브라우저 기본색(검정)으로 떨어진다(실측).
 *
 * hover 는 **색이 아니라 바탕**으로 준다. 색을 밝히면 어두운 데서 좋아지고 밝은 데서 나빠진다 —
 * 한 색으로 양쪽을 다 올릴 수 없다. 바탕을 얹으면 글자 대비를 안 깎고 반응만 더한다.
 */
const ICON_BUTTON_CLASS =
  "absolute right-2 top-1/2 -translate-y-1/2 rounded px-0.5 text-gray-500 " +
  "hover:bg-gray-500/10 focus-visible:bg-gray-500/10 focus:outline-none";

interface Props<T = any> {
  /** 객체 state 폼(useFormState 짝)의 필드 키. 네이티브 폼 화면에선 생략한다 — 아래 「두 모드」 참조. */
  fieldName?: keyof T;
  value?: string | number | null;
  placeholder?: string;
  readOnly?: boolean;
  mode?: "text" | "search" | "tel" | "url" | "email" | "password";
  showPasswordToggle?: boolean;
  mask?: string; // 마스크 패턴 (예: '000-0000-0000') — 제어 모드 전용(아래 주석)
  maskChar?: string;
  maskInvalidMessage?: string;
  visible?: boolean; // 컴포넌트 표시 여부
  onValueChanged?: (fieldName: keyof T, value: any) => void;
  getFieldProps?: (fieldName: keyof T) => any;
  // 네이티브 폼(비제어) 지원 — #341 ⑤ Auth·Policy 이관에서 추가. 종전엔 이 셋이 없어
  // anti-patterns-frontend.md 룰4 예외1(「wrapper 가 name/uncontrolled 미지원」)이 성립했다.
  /** `<label htmlFor>` 연결·포커스 스크립트용. 실제 `<input>` 에 붙는다(래퍼 div 가 아니다). */
  id?: string;
  /** 네이티브 폼 제출(`e.target.<name>.value`)에서 값을 읽기 위한 필드 이름. */
  name?: string;
  /** 비제어 초기값. `value` 없이 이것만 주면 비제어 모드가 된다. */
  defaultValue?: string;
  /**
   * 브라우저 자동완성 통로 (WCAG 1.3.5 AA). `<input>` 이 명시 나열이라 rest 스프레드가 없어
   * **호출부만으로는 못 닫힌다** — 여기 통로가 있어야 한다.
   */
  autoComplete?: string;
  /** 호출부 추가 클래스 — `<input>` 에 마지막으로 붙는다(기본 클래스보다 뒤). */
  className?: string;
  // DevExtreme 기본 props 추가 지원
  width?: number | string;
  height?: number | string;
  disabled?: boolean;
  tabIndex?: number;
  maxLength?: number;
  showClearButton?: boolean;
  onKeyDown?: (e: any) => void;
}

// mask: '0' = 숫자 자리, 그 외 문자는 리터럴로 그 자리에 자동 삽입된다(전화번호형 마스크 기준).
// DevExtreme 마스크 엔진(문자 클래스 'a'/'A'/'*' 등, 완성 전 maskChar placeholder 표시)의 부분
// 집합이다 — 이 wrapper 를 마스크로 쓰는 실 소비자가 0건 확인(전수 grep, #341 오더)이라 그
// 폭까지 재구현하지 않는다. 실사용이 생기면 그때 확장한다.
function applyDigitMask(raw: string, mask: string): string {
  const digits = raw.replace(/\D/g, "");
  let result = "";
  let di = 0;
  for (let i = 0; i < mask.length && di < digits.length; i++) {
    result += mask[i] === "0" ? digits[di++] : mask[i];
  }
  return result;
}

/**
 * 단일 라인 텍스트 입력 컴포넌트 (O8-3, Radix 불필요 — 네이티브 `<input>` 이 이미 폼 시맨틱을 갖춘다)
 *
 * 이름, 제목, 이메일, 전화번호 등 한 줄 텍스트 입력에 사용합니다.
 * mode 속성으로 모바일 최적화 키보드를 제공하고, mask로 입력 형식을 제한할 수 있습니다.
 *
 * ## 두 모드
 *
 * - **제어(controlled)** — `value` + `onValueChanged(fieldName, value)`. `useFormState` 객체 폼
 *   (Admin CRUD)의 기본 계약이다. 기존 소비자 전부가 이 모드다.
 * - **비제어(uncontrolled)** — `name` + `defaultValue`. 값은 제출 시점에 `e.target.<name>.value`
 *   로 읽는다. Auth·Mypage 의 네이티브 폼 화면용(#341 ⑤). `value` 가 없고 `defaultValue` 가
 *   있을 때만 이 모드로 들어간다 — 기존 소비자는 `defaultValue` 를 안 쓰므로 영향받지 않는다
 *   (데이터 도착 전 `value` 가 잠깐 `undefined` 인 폼이 조용히 비제어로 넘어가지 않게 하려고
 *   "`value` 가 undefined 면 비제어"로 추론하지 않는다).
 *
 * `mask` 는 제어 모드 전용이다 — 비제어에선 DOM 값을 되쓸 수 없어 마스크가 화면에 반영되지 않는다.
 *
 * @example
 * // 제어 — 객체 state 폼
 * <TextBox fieldName="phone" value={form.phone} onValueChanged={handleChange} mask="000-0000-0000" />
 *
 * // 비제어 — 네이티브 폼 제출
 * <form onSubmit={(e) => console.log(e.target.email.value)}>
 *   <label htmlFor="email">이메일</label>
 *   <TextBox id="email" name="email" mode="email" defaultValue="" />
 * </form>
 */
export function TextBox<T = any>({
  fieldName,
  value,
  placeholder,
  readOnly = false,
  mode = "text",
  showPasswordToggle = false,
  mask,
  maskChar: _maskChar = "_",
  maskInvalidMessage: _maskInvalidMessage,
  visible = true,
  onValueChanged,
  getFieldProps,
  id,
  name,
  defaultValue,
  autoComplete,
  className,
  width,
  height,
  disabled,
  tabIndex,
  maxLength,
  showClearButton,
  onKeyDown,
}: Props<T>) {
  const [passwordVisible, setPasswordVisible] = useState(false);
  // 검증 에러 메시지 <div> 의 id — invalid 시 input 의 aria-describedby 가 이 id 를 가리켜야
  // 스크린리더가 "잘못됨"뿐 아니라 "왜 잘못됐는지"도 읽는다. useId 는 훅이라 조기 return(아래)
  // 보다 먼저, 그리고 항상 호출한다(훅 순서 규칙) — 실제 DOM 에 쓰이는 건 invalid 일 때뿐이다.
  // 커널 계약: getFieldProps 검증 렌더링 패턴 전체에 적용(.docs/4-아키텍처/터미널-프론트엔드-구조.md
  // §2.7, #391 B2 — main 대비 회귀였다: DevExtreme 은 자체 `dx-…` id 로 이 연결을 자동 생성했다).
  const errorMessageId = useId();

  if (!visible) return null;

  // 기존 DevExtreme 버전과 같은 우선순위: getFieldProps 결과가 명시적 prop 을 덮는다
  // (원래 `{...(getFieldProps ? getFieldProps(fieldName) : {})}` 를 JSX 맨 뒤에 스프레드하던
  // 순서 그대로 — width는 반영, stylingMode 는 네이티브 입력에 대응 개념이 없어 버린다)
  // getFieldProps 는 객체 state 폼 계약의 일부다 — fieldName 이 없는 비제어 화면에선 호출하지 않는다.
  const fieldProps = getFieldProps && fieldName !== undefined ? getFieldProps(fieldName) : undefined;
  const isInvalid = fieldProps?.validationStatus === "invalid";
  const errorMessage: string | undefined = isInvalid
    ? Array.isArray(fieldProps?.validationError)
      ? fieldProps?.validationError[0]?.message
      : fieldProps?.validationError?.message
    : undefined;
  const effectiveWidth = fieldProps?.width ?? width;

  // 비제어 모드 — DOM 이 값의 주인이다. `value` 를 붙이면 React 가 제어로 보고 매 렌더마다
  // 되쓰므로, 두 prop 을 동시에 넘기지 않는다(제어/비제어 전환 경고 방지).
  const isUncontrolled = value === undefined && defaultValue !== undefined;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const next = mask && !isUncontrolled ? applyDigitMask(raw, mask) : raw;
    onValueChanged?.(fieldName as keyof T, next);
  };

  const input = (
    <input
      id={id}
      name={name}
      autoComplete={autoComplete}
      type={showPasswordToggle ? (passwordVisible ? "text" : "password") : mode}
      {...(isUncontrolled ? { defaultValue } : { value: value ?? "" })}
      placeholder={readOnly ? "" : placeholder}
      readOnly={readOnly}
      disabled={disabled}
      tabIndex={tabIndex}
      maxLength={maxLength}
      onChange={handleChange}
      onKeyDown={onKeyDown}
      aria-invalid={isInvalid || undefined}
      aria-describedby={isInvalid && errorMessage ? errorMessageId : undefined}
      style={{ height }}
      className={cn(
        "w-full rounded border px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400",
        "focus:outline-none focus:ring-2 focus:ring-blue-500/40",
        "read-only:cursor-default read-only:bg-gray-50",
        "disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400",
        isInvalid ? "border-[#d9534f]" : "border-gray-300",
        showClearButton && value ? "pr-8" : "",
        showPasswordToggle ? "pr-8" : "",
        className,
      )}
    />
  );

  // 폭 미지정 시 부모(대개 TableCell)의 100% 를 채운다 — inline-flex 로 shrink-wrap 하면
  // width:100% 인 input 과 순환 참조가 생겨 0폭으로 무너진다. 실사용 전수(#341 오더)에서 폭을
  // 명시하는 호출부가 없었고 getFieldProps 는 항상 width:"100%" 를 반환하므로, block 기반
  // 100% 기본값(className)이 실제 관측된 쓰임과 그대로 맞는다. effectiveWidth 가 명시되면
  // inline style 이 그 클래스를 덮는다(cn.ts 가 클래스 충돌을 안 풀어주므로 폭은 항상 style).
  return (
    <div className="flex w-full flex-col">
      <div className="relative w-full" style={{ width: effectiveWidth }}>
        {input}
        {showClearButton && !!value && !showPasswordToggle && (
          <button
            type="button"
            aria-label="지우기"
            className={ICON_BUTTON_CLASS}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onValueChanged?.(fieldName as keyof T, "")}
          >
            ×
          </button>
        )}
        {showPasswordToggle && (
          <button
            type="button"
            aria-label={passwordVisible ? "비밀번호 숨기기" : "비밀번호 표시"}
            className={ICON_BUTTON_CLASS}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setPasswordVisible((v) => !v)}
          >
            <Icon name={passwordVisible ? "eyeopen" : "eyeclose"} size={18} />
          </button>
        )}
      </div>
      {isInvalid && errorMessage && (
        <div id={errorMessageId} className="mt-1 self-start rounded bg-[#d9534f] p-2 text-xs leading-normal text-white">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
