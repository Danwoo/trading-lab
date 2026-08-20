// components/shared/ui/primitives/FieldShell.tsx
//
// 폼 프리미티브의 공통 껍데기 (#341 ②) — 폭 컨테이너 + 검증 에러 메시지.
// TextBox 가 인라인으로 갖고 있던 구조(#391 B2)를 그대로 올린 것이라 시각적 결과가 같다 —
// 그 TextBox 도 이제 사본을 버리고 이 껍데기를 쓴다(#281).
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
        <div id={errorMessageId} className="mt-1 self-start rounded bg-danger p-2 text-xs leading-normal text-bg-base">
          {errorMessage}
        </div>
      )}
    </div>
  );
}

/**
 * 모든 텍스트형 입력이 공유하는 기본 클래스. **여기 한 벌만 있다** — 프리미티브가 같은 네 줄을
 * 따로 갖고 있으면 한쪽만 고쳐도 그물이 초록이고, 실제로 TextBox 가 사본을 갖고 있었다.
 *
 * **바탕을 반드시 준다.** 종전에는 배경 클래스가 아예 없어 브라우저 기본(흰색)으로 떨어졌고,
 * 그래서 이 입력이 다크 보드 위에서 흰 상자가 됐다. 대비 검사로는 안 잡힌다 — 흰 바탕에
 * 다크 잉크는 대비가 **높기** 때문이다. 잡히는 것은 눈으로 볼 때뿐이다.
 *
 * **그 바탕은 `--bg-base` 다 — 이 레포에서 입력을 담는 그릇이 절대 쓰지 않는 유일한 표면
 * 토큰이기 때문이다.** 입력이 실제로 놓이는 그릇을 전수 조사하면 `--bg-panel`(BoardZone·
 * 로그인 카드·SelectMenu 팝오버), `--bg-raised`(IngestConsole 구역), 라이트 `#FFFFFF`
 * (/admin 다이얼로그)·`#F0F1F2`(회원가입 카드)뿐이고 `--bg-base` 는 없다. 그래서 채움이
 * 그릇과 같은 색이 되는 자리가 생기지 않는다 — `--bg-panel` 을 쓰면 BoardZone 위에서,
 * `--bg-raised` 를 쓰면 IngestConsole 구역 위에서 각각 1.00:1 이 된다.
 *
 * 방향도 두 모드에서 같다 — `--bg-base` 는 다크·라이트 양쪽에서 `--bg-panel` 보다 어두워
 * 언제나 「파인 자리」로 읽힌다(`--bg-raised` 는 다크에서 밝고 라이트에서 어두워 방향이
 * 뒤집힌다). 테두리도 이 바탕에서 더 갈린다: `--line` on `--bg-base` 1.34:1 >
 * on `--bg-panel` 1.24:1. 같은 논리를 손으로 쓴 입력 둘이 이미 따르고 있다 —
 * `SelectMenu.tsx` 의 팝오버 검색 입력과 `IngestConsole.tsx` 의 주기 select.
 *
 * `--bg-raised` 는 `read-only`/`disabled` 가 쓴다. 디자인 시스템 §1.1 은 그 토큰에
 * 「입력 배경」을 적어 두었는데, 그 표는 입력이 `--bg-raised` 구역 안에 놓이는 경우를 아직
 * 담고 있지 않다 — 표를 이 조사 결과에 맞추는 것은 정본 문서의 결정이라 이 PR 이 하지 않고
 * 본문 「발견」으로 올린다.
 *
 * **포커스 링을 여기서 그리지 않는다.** 포커스 표시의 정본은 `globals.css` 의
 * `:focus-visible { outline: … dashed rgb(var(--ink-strong)) }` 한 자리다. 여기에
 * `focus:outline-none` 을 두면 명시도(0,2,0)가 그 정본(0,1,0)을 덮어 **키보드 포커스 표시를
 * 지우고**, 대신 남는 `ring-line-strong` 은 `--bg-panel` 대비 1.8:1 로 WCAG 1.4.11(3:1)에
 * 못 미친다.
 */
export const FIELD_INPUT_CLASS =
  "w-full rounded border bg-bg-base px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted " +
  "read-only:cursor-default read-only:bg-bg-raised " +
  "disabled:cursor-not-allowed disabled:bg-bg-raised disabled:text-ink-muted";

export function fieldBorderClass(isInvalid: boolean): string {
  return isInvalid ? "border-danger" : "border-line";
}

/**
 * 입력 안에 겹쳐 그리는 아이콘 버튼(클리어·비밀번호 토글·달력 열기)의 클래스.
 *
 * **잉크는 토큰으로 준다** — 셸이 선언한 테마를 따라간다. 종전에는 `text-gray-400/500` 에
 * `hover:text-gray-600/700` 이라 hover 색이 밝은 바탕 전제였고, 어두운 셸에서는 **대비가
 * 1.57:1 로 떨어져 마우스를 올리면 아이콘이 사라졌다**. 원시 회색을 쓸 수밖에 없던 이유였던
 * 「`/admin` 셸이 `data-theme="light"` 를 선언하지 않는다」는 전제는 없어졌다(#281).
 *
 * 왜 `text-current` 는 아닌가: 이 래퍼에는 잉크가 없어 브라우저 기본색으로 떨어진다(실측).
 *
 * hover 는 **색이 아니라 바탕**으로 준다. 색을 밝히면 어두운 데서 좋아지고 밝은 데서 나빠진다 —
 * 한 색으로 양쪽을 다 올릴 수 없다. 바탕을 얹으면 글자 대비를 안 깎고 반응만 더한다.
 *
 * 크기는 `ICON_HIT_AREA` 가 정한다 — 24×24 상자 안에 글리프를 가운데 두므로 보이는 크기는
 * 그대로다(#289). `right-2`(8) + 24 = 32 = 입력의 `pr-8` 이라 글자를 안 덮는다.
 */
export const FIELD_ICON_BUTTON_CLASS =
  `${ICON_HIT_AREA} absolute right-2 top-1/2 -translate-y-1/2 rounded text-ink-muted ` +
  "hover:bg-bg-raised focus-visible:bg-bg-raised";
