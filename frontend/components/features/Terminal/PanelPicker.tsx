"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { listPanelDefinitions } from "@/lib/terminal/panelRegistry";
import type { PanelDefinition } from "@/types/terminal/panel";
import type { PanelInstance } from "@/types/terminal/layout";

export interface PanelPickerProps {
  panels: PanelInstance[];
  onAdd: (definition: PanelDefinition) => void;
}

/**
 * 닫힌 패널을 다시 여는 UI. 레지스트리 중 현재 레이아웃에 없는 타입만 보여준다 (T3-5).
 * O3 는 레지스트리를 빈 채로 land 하므로, 이 목록은 O6 전까지 항상 빈 상태다 — 그 상태도
 * "빈 화면"이 아니라 이유가 적힌 빈 상태로 보여준다.
 *
 * #314 — WAI-ARIA menu button 키보드 모델을 `PanelMenu.tsx`(같은 터미널 드롭다운 표면)와
 * 맞춘다: 항목은 roving tabindex(`tabIndex={-1}`, 화살표 키로만 이동)이고, `Tab` 은 메뉴를
 * 그대로 닫는다(포커스가 루트 밖으로 나가기 전에 닫으므로, "포커스가 루트 밖이면 Escape 를
 * 못 잡는" 문제 자체가 생기지 않는다 — 이슈가 제안한 두 해소안 중 "focusout 으로 루트를
 * 벗어나면 닫는다"와 같은 효과를 Tab 자체를 닫힘 신호로 다뤄서 낸다). 키 핸들러는
 * `PanelMenu.tsx` 와 달리 **루트 div**(트리거+메뉴를 모두 감싼다)에 둔다 — 레지스트리가
 * 비면(T3-2) 포커스 가능한 항목이 없어 포커스가 트리거에 남는데, 핸들러를 메뉴 div 안에만
 * 두면 그 경우 버블링으로 못 잡는다(형제 요소는 이벤트를 안 받는다).
 */
export function PanelPicker({ panels, onAdd }: PanelPickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const openTypes = new Set(panels.map((panel) => panel.type));
  const closedDefinitions = listPanelDefinitions().filter((def) => !openTypes.has(def.type));
  // 매 렌더 다시 채운다 — 항목 수가 레지스트리·레이아웃에 따라 바뀌므로, 이전 렌더의 배열을
  // 그대로 두면 줄어든 뒤 꼬리에 unmount 된 버튼 참조가 남는다.
  itemRefs.current = [];

  useEffect(() => {
    if (open) itemRefs.current[0]?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  const handleRootKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!open) return;
    const count = itemRefs.current.length;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (count === 0) return;
      const currentIndex = itemRefs.current.findIndex((el) => el === document.activeElement);
      itemRefs.current[(currentIndex + 1) % count]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (count === 0) return;
      const currentIndex = itemRefs.current.findIndex((el) => el === document.activeElement);
      itemRefs.current[(currentIndex - 1 + count) % count]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      close(false);
    }
  };

  return (
    <div className="relative" ref={rootRef} onKeyDown={handleRootKeyDown}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="border border-slate-line px-2 py-1 font-mono text-xs text-ink-primary hover:bg-slate-line"
      >
        패널 추가
      </button>
      {open && (
        <div
          role="menu"
          aria-label="닫힌 패널 목록"
          className="absolute right-0 z-10 mt-1 w-56 border border-slate-line bg-slate-panel py-1 font-mono text-xs shadow-lg"
        >
          {closedDefinitions.length === 0 ? (
            <p role="status" className="px-3 py-2 text-ink-muted">
              등록된 패널이 없습니다.
            </p>
          ) : (
            closedDefinitions.map((definition, index) => (
              <button
                key={definition.type}
                ref={(el) => {
                  itemRefs.current[index] = el;
                }}
                role="menuitem"
                type="button"
                tabIndex={-1}
                onClick={() => {
                  onAdd(definition);
                  close(true);
                }}
                className="block w-full px-3 py-1.5 text-left text-ink-primary hover:bg-slate-line focus-visible:bg-slate-line"
              >
                {definition.title}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
