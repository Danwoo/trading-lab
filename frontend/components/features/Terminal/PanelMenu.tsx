"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

export interface PanelMenuProps {
  collapsed: boolean;
  onMove: (direction: "up" | "down" | "left" | "right") => void;
  onResize: (axis: "w" | "h", delta: number) => void;
  onToggleCollapse: () => void;
  onClose: () => void;
}

interface MenuAction {
  label: string;
  run: () => void;
}

/**
 * 헤더 줄 끝의 패널 조작 메뉴 — RGL 은 키보드 핸들러·ARIA 가 0 이라(#242 O1 스파이크),
 * 이동·크기·접기·닫기의 유일한 키보드 경로가 여기다. WAI-ARIA Menu Button 패턴 (역할=menu).
 */
export function PanelMenu({ collapsed, onMove, onResize, onToggleCollapse, onClose }: PanelMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const actions: MenuAction[] = [
    { label: "위로 이동", run: () => onMove("up") },
    { label: "아래로 이동", run: () => onMove("down") },
    { label: "왼쪽으로 이동", run: () => onMove("left") },
    { label: "오른쪽으로 이동", run: () => onMove("right") },
    { label: "너비 늘리기", run: () => onResize("w", 1) },
    { label: "너비 줄이기", run: () => onResize("w", -1) },
    { label: "높이 늘리기", run: () => onResize("h", 1) },
    { label: "높이 줄이기", run: () => onResize("h", -1) },
    { label: collapsed ? "펼치기" : "접기", run: onToggleCollapse },
    { label: "닫기", run: onClose },
  ];

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

  const runAction = (action: MenuAction) => {
    action.run();
    close(true);
  };

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = itemRefs.current.findIndex((el) => el === document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const next = (currentIndex + 1) % actions.length;
      itemRefs.current[next]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      const prev = (currentIndex - 1 + actions.length) % actions.length;
      itemRefs.current[prev]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      close(false);
    }
  };

  return (
    <div className="relative panel-no-drag" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="패널 메뉴"
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          // WAI-ARIA menu button 패턴은 ArrowDown 으로도 열고 첫 항목에 포커스를 준다
          // (#314) — 지금까지는 Enter/Space(버튼 기본 활성화)만 열었다. 이미 열려 있으면
          // 이 핸들러는 아무것도 하지 않는다(그 경우 포커스가 이미 메뉴 안으로 옮겨가 있어
          // 이 트리거의 keydown 자체가 발생하지 않는다).
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className="rounded-sm px-1 text-ink-muted hover:text-ink-primary focus-visible:text-ink-primary"
      >
        ⋮
      </button>
      {open && (
        <div
          role="menu"
          aria-label="패널 조작"
          onKeyDown={handleMenuKeyDown}
          className="absolute right-0 z-10 mt-1 w-40 border border-slate-line bg-slate-panel py-1 text-xs shadow-lg"
        >
          {actions.map((action, index) => (
            <button
              key={action.label}
              ref={(el) => {
                itemRefs.current[index] = el;
              }}
              role="menuitem"
              type="button"
              tabIndex={-1}
              onClick={() => runAction(action)}
              className="block w-full px-3 py-1.5 text-left text-ink-primary hover:bg-slate-line focus-visible:bg-slate-line"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
