// components/shared/ui/Button.tsx
import React from "react";
import { cn } from "./primitives/cn";
import { Icon } from "./primitives/icons";

export interface Props {
  text?: string;
  onClick?: () => void;
  type?: "default" | "success" | "normal" | "danger";
  stylingMode?: "contained" | "outlined" | "text";
  icon?: string;
  width?: number | string;
  height?: number | string;
  disabled?: boolean;
  visible?: boolean;
  className?: string;
  style?: React.CSSProperties;
  useSubmitBehavior?: boolean;
  render?: () => React.ReactNode;
  hint?: string;
  elementAttr?: Record<string, any>;
}

/** ButtonProps에 sort를 더한 액션 버튼 타입. 패널/훅 내부 순서 제어에만 사용됩니다. */
export type ActionButton = Props & { sort?: number };

// type(색 의미) × stylingMode(채움 방식) 조합 — 실사용 12조합 전부 확인함(messageStore.ts 기본값
// + MessagePopup/WatchlistDetailForm 등). 이 레포에 버튼 전용 디자인 토큰이 없어(§ 디자인 토큰
// 문서는 터미널 전용 slate/ink/signal/market 뿐) Tailwind 기본 팔레트를 직접 쓴다 — 다른 자체
// 구현 프리미티브(CheckBoxGroup.tsx 등)와 같은 관례.
const VARIANT_CLASSES: Record<Props["type"] & string, Record<Props["stylingMode"] & string, string>> = {
  default: {
    contained: "bg-blue-600 text-white border border-blue-600 hover:bg-blue-700 hover:border-blue-700",
    outlined: "bg-transparent text-blue-600 border border-blue-600 hover:bg-blue-50",
    text: "bg-transparent text-blue-600 border border-transparent hover:bg-blue-50",
  },
  success: {
    contained: "bg-green-600 text-white border border-green-600 hover:bg-green-700 hover:border-green-700",
    outlined: "bg-transparent text-green-600 border border-green-600 hover:bg-green-50",
    text: "bg-transparent text-green-600 border border-transparent hover:bg-green-50",
  },
  normal: {
    contained: "bg-gray-200 text-gray-800 border border-gray-200 hover:bg-gray-300 hover:border-gray-300",
    outlined: "bg-transparent text-gray-700 border border-gray-300 hover:bg-gray-50",
    text: "bg-transparent text-gray-700 border border-transparent hover:bg-gray-100",
  },
  danger: {
    // #d9534f — 이 레포의 기존 에러색 관례(CheckBoxGroup.tsx invalid 배지)와 맞춘다
    contained: "bg-[#d9534f] text-white border border-[#d9534f] hover:bg-[#c9302c] hover:border-[#c9302c]",
    outlined: "bg-transparent text-[#d9534f] border border-[#d9534f] hover:bg-[#d9534f]/10",
    text: "bg-transparent text-[#d9534f] border border-transparent hover:bg-[#d9534f]/10",
  },
};

/**
 * 버튼 컴포넌트 (O8-3, Radix 불필요 — 네이티브 `<button>` 이 이미 포커스·키보드·역할을 갖춘다)
 *
 * width/height props와 style 병합, 조건부 렌더링, `render` 커스텀 콘텐츠를 지원합니다.
 *
 * `icon` 은 이관 전 DevExtreme 아이콘 이름을 그대로 받는다 — 글리프만 `react-icons` 로 옮겼다
 * (`primitives/icons.tsx`, #341). 아이콘만 있고 글자가 없는 버튼은 `hint` 가 접근명이 된다.
 *
 * @example
 * <Button text="저장" type="success" onClick={handleSave} />
 */
export const Button: React.FC<Props> = ({
  text,
  onClick,
  type = "default",
  stylingMode = "contained",
  icon,
  width,
  height,
  disabled = false,
  visible = true,
  className,
  style,
  useSubmitBehavior = false,
  render,
  hint,
  elementAttr,
}) => {
  if (!visible) return null;

  const combinedStyle: React.CSSProperties = {
    ...(width !== undefined && { width }),
    ...(height !== undefined && { height }),
    ...style,
  };

  const elementClass: string | undefined = typeof elementAttr?.class === "string" ? elementAttr.class : undefined;
  const elementRest = elementAttr
    ? Object.fromEntries(Object.entries(elementAttr).filter(([k]) => k !== "class"))
    : undefined;

  return (
    <button
      type={useSubmitBehavior ? "submit" : "button"}
      onClick={onClick}
      disabled={disabled}
      title={hint}
      style={combinedStyle}
      // 아이콘만 있는 버튼은 보이는 글자가 없다 — `hint`(title) 를 접근명으로 승격시킨다.
      aria-label={!text && !render && hint ? hint : undefined}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors",
        "focus:outline-none focus:ring-2 focus:ring-blue-500/40",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT_CLASSES[type][stylingMode],
        className,
        elementClass,
      )}
      {...elementRest}
    >
      {render ? (
        render()
      ) : (
        <>
          {icon && <Icon name={icon} />}
          {text}
        </>
      )}
    </button>
  );
};

export default Button;
