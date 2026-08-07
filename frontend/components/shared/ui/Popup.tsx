"use client";

import React, { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent } from "./primitives/dialog";

export interface Props {
  visible: boolean;
  title?: string;
  width?: number | string;
  height?: number | string;
  onHiding?: () => void;
  showCloseButton?: boolean;
  dragEnabled?: boolean;
  resizeEnabled?: boolean;
  children?: React.ReactNode;
  contentRender?: () => React.ReactNode;
  className?: string;
  position?: any;
  animation?: any;
  shading?: boolean;
  shadingColor?: string;
  hideOnOutsideClick?: boolean | ((e: any) => boolean);
  showTitle?: boolean;
  rtlEnabled?: boolean;
  maxWidth?: number | string;
  maxHeight?: number | string;
  minWidth?: number | string;
  minHeight?: number | string;
  fullScreen?: boolean;
  hideOnParentScroll?: boolean;
  container?: string | Element;
  wrapperAttr?: any;
}

/**
 * 모달 팝업 컴포넌트
 *
 * - Radix Dialog + Tailwind 래핑 (O8-3, DevExtreme Popup 대체 — `primitives/dialog.tsx` 가 커널)
 * - `shading` 은 배경 유무만 토글한다. Radix Dialog 는 항상 modal(포커스 트랩 + 배경 상호작용
 *   차단)이고, 실사용 중 `shading=false` 로 비모달을 기대하는 호출부는 없다(확인함 — 0건).
 * - `hideOnOutsideClick` 기본 true. 함수 형태(`(e) => boolean`)도 지원한다.
 * - 드래그는 상단 그랩 영역(제목이 보이면 그 줄 전체, 아니면 얇은 2px 스트립)의 pointer 이벤트로
 *   직접 구현했다(신규 의존성 없이, #341 오더). 리사이즈는 커스텀 핸들 대신 네이티브 CSS
 *   `resize: both`(Tailwind `resize` 유틸리티)를 쓴다 — 브라우저 표준 리사이즈 그립이라
 *   접근성·구현 비용 양쪽에서 커스텀 핸들보다 낫다.
 *
 * **확인 안 함 / no-op(0 실사용 확인, 타입만 유지)**: `position`(DevExtreme 위치 설정 객체 —
 * Radix 는 항상 뷰포트 중앙 고정), `animation`(인스턴스별 커스텀 애니메이션 — 대신 고정된
 * fade+scale 트랜지션 하나, `motion-reduce:` 시 자동 비활성), `hideOnParentScroll`.
 * 실사용이 생기면 그때 구현한다.
 */
export function Popup({
  visible,
  title,
  width = "auto",
  height = "auto",
  onHiding,
  showCloseButton = true,
  dragEnabled = true,
  resizeEnabled = false,
  children,
  contentRender,
  className,
  position: _position,
  animation: _animation,
  shading = true,
  shadingColor,
  hideOnOutsideClick = true,
  showTitle = true,
  rtlEnabled = false,
  maxWidth,
  maxHeight,
  minWidth,
  minHeight,
  fullScreen = false,
  hideOnParentScroll: _hideOnParentScroll,
  container,
  wrapperAttr,
}: Props) {
  const [drag, setDrag] = useState({ x: 0, y: 0 });
  const dragStateRef = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // 팝업이 닫혔다 다시 열리면 드래그 오프셋 초기화 — DevExtreme Popup 도 매번 기본 위치로 연다.
  // 열릴 때는 트리거 요소를 기억해 뒀다가(아래 onCloseAutoFocus) 닫힐 때 포커스를 되돌린다 —
  // 이 Popup 은 `Dialog.Trigger` 없이 외부 상태(messageStore 등)로 열고 닫혀서, Radix 의
  // 기본 close-autofocus 복원이 트리거를 추적하지 못한다(실측 확인 — #341 오더, 키보드로 삭제
  // 확인 팝업을 열고 Escape 로 닫으면 포커스가 body 로 빠졌다).
  useEffect(() => {
    if (visible) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    } else {
      setDrag({ x: 0, y: 0 });
    }
  }, [visible]);

  useEffect(() => {
    if (!dragEnabled) return;
    const handleMove = (e: PointerEvent) => {
      const st = dragStateRef.current;
      if (!st) return;
      setDrag({ x: st.originX + (e.clientX - st.startX), y: st.originY + (e.clientY - st.startY) });
    };
    const handleUp = () => {
      dragStateRef.current = null;
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, [dragEnabled]);

  const handleDragStart = (e: React.PointerEvent) => {
    if (!dragEnabled) return;
    dragStateRef.current = { startX: e.clientX, startY: e.clientY, originX: drag.x, originY: drag.y };
  };

  const shouldHideOnOutside = (e: any): boolean =>
    typeof hideOnOutsideClick === "function" ? hideOnOutsideClick(e) : hideOnOutsideClick;

  /**
   * 열릴 때 포커스를 **본문 안의 첫 조작 요소**에 둔다 — 스크롤 영역 자신이 아니라.
   *
   * 스크롤 영역에 `tabIndex={0}` 을 준 순간(#404) 그것이 다이얼로그의 첫 tabbable 이 되어,
   * Radix 기본 동작이 본문 컨테이너에 포커스를 준다. 그러면 알림 팝업을 열고 Enter 로 바로
   * 확인하던 경로가 조용히 죽는다(종전엔 「확인」 버튼이 첫 tabbable 이었다 — 실측).
   * 그래서 종전 포커스 위치를 그대로 복원한다. 본문에 조작 요소가 하나도 없으면(약관 같은
   * 읽기 전용 팝업) 스크롤 영역 자신에 둔다 — 그래야 키보드로 바로 스크롤할 수 있다.
   */
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const focusInitialTarget = (e: Event) => {
    const scroller = scrollAreaRef.current;
    if (!scroller) return;
    e.preventDefault();
    const candidates = scroller.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    // 후보를 순서대로 실제로 focus 해 보고 **먹었는지**로 판정한다(Radix `focusFirst` 와 같은
    // 방식). 숨은 요소(display:none 등)는 focus 가 먹지 않으므로 자연히 걸러진다 —
    // `getClientRects()` 같은 레이아웃 질의로 거르면 레이아웃이 없는 jsdom 에서 전부 탈락한다.
    // `preventScroll` 은 Radix 기본 동작과 맞추는 것이다 — 그게 없으면 브라우저가 포커스 대상을
    // 보이게 하려고 본문을 끝까지 스크롤한다(약관 팝업처럼 버튼이 긴 본문 아래에 있으면 열자마자
    // 맨 아래가 보인다 — 실측 scrollTop 1371).
    const focused = Array.from(candidates).some((el) => {
      el.focus({ preventScroll: true });
      return document.activeElement === el;
    });
    if (!focused) scroller.focus({ preventScroll: true });
  };

  // DevExtreme `wrapperAttr` 는 `{ class, id, ... }` 한 덩어리로 팝업 래퍼 엘리먼트 하나에
  // 붙는 계약이다. `class` 만 분리하는 이유는 우리가 만든 클래스와 합쳐야 하기 때문이고,
  // 분리한 둘은 **같은 노드**(DialogContent = 다이얼로그 박스)로 다시 모인다 — 계약이 갈리지
  // 않는다. (한때 Content 바깥에 전체 뷰포트 래퍼가 있어서 class 는 안쪽 박스로, 나머지 속성은
  // 바깥 래퍼로 갈라졌었다. 그 래퍼는 #391 N1 로 제거됐다.)
  const wrapperClass: string | undefined = typeof wrapperAttr?.class === "string" ? wrapperAttr.class : undefined;
  const wrapperRest = wrapperAttr
    ? Object.fromEntries(Object.entries(wrapperAttr).filter(([k]) => k !== "class"))
    : undefined;

  return (
    <Dialog open={visible} onOpenChange={(open) => !open && onHiding?.()}>
      <DialogContent
        accessibleTitle={title || "팝업"}
        showVisibleTitle={showTitle && !!title}
        visibleTitle={title}
        container={container as HTMLElement | undefined}
        showCloseButton={showCloseButton}
        shadingColor={shadingColor}
        transparentOverlay={!shading}
        dir={rtlEnabled ? "rtl" : undefined}
        className={[className, wrapperClass, resizeEnabled ? "resize overflow-auto" : "overflow-hidden"]
          .filter(Boolean)
          .join(" ")}
        // 드래그 오프셋은 `style.transform` 이 아니라 `offset` prop 으로 넘긴다 — 커널이
        // 중앙정렬과 같은 `translate` 프로퍼티에 합성한다(primitives/dialog.tsx 불변식 (2)).
        // `transform` 은 열림/닫힘 keyframes 전용이다: 거기에 위치를 실으면 애니메이션이 도는
        // 150ms 동안 keyframes 가 그 값을 덮어쓰고 종료 시 되돌아온다 — B1 이 정확히 그 사고였다.
        offset={drag}
        style={
          fullScreen
            ? { width: "100vw", height: "100vh", borderRadius: 0 }
            : { width, height, minWidth, minHeight, maxWidth, maxHeight }
        }
        onPointerDownOutside={(e) => {
          if (!shouldHideOnOutside(e)) e.preventDefault();
        }}
        onOpenAutoFocus={focusInitialTarget}
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          previouslyFocusedRef.current?.focus?.();
        }}
        {...wrapperRest}
      >
        {dragEnabled && (
          <div
            role="presentation"
            aria-hidden="true"
            onPointerDown={handleDragStart}
            className={
              showTitle && title
                ? "absolute inset-x-0 top-0 h-10 cursor-move"
                : "absolute inset-x-0 top-0 h-2 cursor-move"
            }
          />
        )}
        {/*
          본문 스크롤 영역. `tabIndex={0}` 이 없으면 **마우스로 본문을 한 번 클릭한 순간
          키보드 스크롤이 죽는다**(#404 — 실브라우저 실측). 클릭 지점에 포커스 가능한 요소가
          없으면 브라우저는 가장 가까운 포커스 가능 조상을 잡는데, 그게 `DialogContent`
          (Radix 가 `tabindex="-1"` 을 붙인다 · 여기서는 `overflow-hidden`)라 PageDown 이
          스크롤할 대상을 못 찾는다. Chromium 의 keyboard-focusable scrollers 도 이 컨테이너를
          구제하지 못한다 — 그 기능은 포커스 가능한 자식이 없는 스크롤러에만 적용되는데, 이
          안에는 버튼이 들어온다(MessagePopup 의 확인/취소).
          포커스를 받는 스크롤 영역은 보조기술에 이름과 역할이 있어야 하므로 `role="region"` +
          `aria-label` 을 함께 단다(이름 없는 region 은 노출되지 않는다).
          포커스 링은 `focus-visible:` 로만 그린다 — 마우스 클릭에는 안 뜨고 Tab 으로 왔을 때만
          떠서, 키보드 사용자가 지금 어디에 있는지 잃지 않는다(`FormModal` 은 `outline-none`
          으로 링을 통째로 지웠는데 그러면 그 단서가 사라진다).
        */}
        <div
          ref={scrollAreaRef}
          tabIndex={0}
          role="region"
          aria-label={title || "팝업"}
          className={
            "min-h-0 flex-1 overflow-auto p-4 " +
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40"
          }
        >
          {contentRender ? contentRender() : children}
        </div>
      </DialogContent>
    </Dialog>
  );
}
