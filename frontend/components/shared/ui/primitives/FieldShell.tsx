// components/shared/ui/primitives/FieldShell.tsx
//
// 폼 프리미티브의 공통 껍데기 (#341 ②) — 폭 컨테이너 + 검증 에러 메시지.
// TextBox 가 인라인으로 갖고 있던 구조(#391 B2)를 그대로 올린 것이라 시각적 결과가 같다.
//
// 에러 메시지 `<div>` 의 id 를 입력 요소가 `aria-describedby` 로 가리켜야 스크린리더가 "잘못됨"
// 뿐 아니라 "왜 잘못됐는지"까지 읽는다 — 그래서 id 를 이 컴포넌트가 만들지 않고 **호출부가
// `useId()` 로 만들어 내려준다**(입력 요소와 메시지가 같은 id 를 봐야 하는데, 입력 요소는 이
// 컴포넌트 바깥에 있다).
"use client";

import type { ReactNode } from "react";

import { ICON_HIT_AREA } from "./hitArea";

interface Props {
  children: ReactNode;
  isInvalid: boolean;
  errorMessage?: string;
  /** 입력 요소의 `aria-describedby` 가 가리키는 id — 호출부의 `useId()` 값. */
  errorMessageId: string;
  /** `getFieldProps().width` 가 반영된 최종 폭. 미지정이면 부모 폭 100%. */
  width?: number | string;
  /** 입력 옆에 겹쳐 그리는 요소(지우기 버튼 등)를 위해 `relative` 를 유지한다. */
  className?: string;
}

export function FieldShell({ children, isInvalid, errorMessage, errorMessageId, width, className }: Props) {
  return (
    <div className="flex w-full flex-col">
      <div className={className ?? "relative w-full"} style={{ width }}>
        {children}
      </div>
      {isInvalid && errorMessage && (
        <div id={errorMessageId} className="mt-1 self-start rounded bg-[#d9534f] p-2 text-xs leading-normal text-white">
          {errorMessage}
        </div>
      )}
    </div>
  );
}

/** 모든 텍스트형 입력이 공유하는 기본 클래스 — TextBox 가 쓰던 것과 같다. */
export const FIELD_INPUT_CLASS =
  "w-full rounded border px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500/40 " +
  "read-only:cursor-default read-only:bg-gray-50 " +
  "disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400";

export function fieldBorderClass(isInvalid: boolean): string {
  return isInvalid ? "border-[#d9534f]" : "border-gray-300";
}

/**
 * 입력 안에 겹쳐 그리는 아이콘 버튼(클리어·비밀번호 토글·달력 열기)의 클래스.
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
 *
 * 크기는 `ICON_HIT_AREA` 가 정한다 — 24×24 상자 안에 글리프를 가운데 두므로 보이는 크기는
 * 그대로다(#289). `right-2`(8) + 24 = 32 = 입력의 `pr-8` 이라 글자를 안 덮는다.
 */
export const FIELD_ICON_BUTTON_CLASS =
  `${ICON_HIT_AREA} absolute right-2 top-1/2 -translate-y-1/2 rounded text-gray-500 ` +
  "hover:bg-gray-500/10 focus-visible:bg-gray-500/10 focus:outline-none";
