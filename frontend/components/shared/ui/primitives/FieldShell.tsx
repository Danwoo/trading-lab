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

/**
 * 모든 텍스트형 입력이 공유하는 기본 클래스.
 *
 * **바탕을 반드시 준다.** 종전에는 배경 클래스가 아예 없어 브라우저 기본(흰색)으로 떨어졌고,
 * 그래서 이 입력이 다크 보드 위에서 흰 상자가 됐다. 대비 검사로는 안 잡힌다 — 흰 바탕에
 * 다크 잉크는 대비가 **높기** 때문이다. 잡히는 것은 눈으로 볼 때뿐이다.
 */
export const FIELD_INPUT_CLASS =
  "w-full rounded border bg-bg-panel px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted " +
  "focus:outline-none focus:ring-2 focus:ring-line-strong " +
  "read-only:cursor-default read-only:bg-bg-raised " +
  "disabled:cursor-not-allowed disabled:bg-bg-raised disabled:text-ink-muted";

export function fieldBorderClass(isInvalid: boolean): string {
  return isInvalid ? "border-danger" : "border-line";
}
