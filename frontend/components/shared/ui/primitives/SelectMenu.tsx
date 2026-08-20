// components/shared/ui/primitives/SelectMenu.tsx
//
// 드롭다운 선택 커널 (#341 ②) — `SelectBox`(단일)와 `TagBox`(다중)가 **같은 구현**을 공유한다.
// DevExtreme `SelectBox`/`TagBox` 는 내부가 같은 위젯이었고 호출부 계약(`items`/`displayExpr`/
// `valueExpr`/`searchEnabled`/`acceptCustomValue`/`itemRender`/`fieldRender`)도 같다 — 둘로
// 나눠 구현하면 키보드·ARIA 배선이 한쪽만 고쳐지는 사고가 난다.
//
// **왜 Radix `Select` 가 아니라 `Popover` 인가**: Radix `Select` 는 검색 입력·커스텀 값 입력·
// 다중 선택을 지원하지 않는다(네이티브 select 의미론을 따르는 위젯이라 의도된 제약). 이 레포
// 호출부는 셋 다 쓴다(전수 실측 #341 ② — `searchEnabled` 3곳 · `acceptCustomValue` 3곳 ·
// `itemRender`/`fieldRender` 7곳). 그래서 오버레이·바깥클릭·ESC·포커스 복귀만 Radix `Popover`
// 에 맡기고, 목록 의미론(`listbox`/`option`)은 WAI-ARIA 패턴대로 직접 배선한다.
//
// **포커스 모델**: 팝업이 열리면 포커스는 검색 입력(검색이 꺼져 있으면 목록)에 있고, 강조된
// 항목은 `aria-activedescendant` 로 가리킨다 — 포커스를 항목마다 옮기면 검색 입력에 글자를 칠
// 수 없다. 이것이 "검색 있는 listbox" 의 표준 배선이다.
//
// `dialog.tsx` 의 오버레이 불변식(중간 노드 금지)은 여기 해당하지 않는다 — Popover 는 모달이
// 아니라 딤 오버레이 노드 자체가 없고, 바깥 클릭 판정은 트리거+콘텐츠 두 노드로만 이뤄진다.
"use client";

import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { cn } from "./cn";
import { ICON_HIT_AREA } from "./hitArea";

export interface SelectMenuProps {
  /** 선택지. 문자열 배열이면 `displayExpr`/`valueExpr` 는 무시된다. */
  items: any[];
  displayExpr: string;
  valueExpr: string;
  /** 단일 모드면 값 하나, 다중 모드면 값 배열. */
  value: any;
  multiple?: boolean;
  placeholder?: string;
  readOnly?: boolean;
  disabled?: boolean;
  searchEnabled?: boolean;
  acceptCustomValue?: boolean;
  noDataText?: string;
  showClearButton?: boolean;
  /** 다중 모드에서 태그를 접기 시작하는 개수. */
  maxDisplayedTags?: number;
  /** 다중 모드에서 각 항목에 체크박스를 그린다. */
  showSelectionControls?: boolean;
  width?: number | string;
  height?: number | string;
  itemRender?: (item: any) => ReactNode;
  fieldRender?: (item: any) => ReactNode;
  isInvalid?: boolean;
  /** 검증 실패 시 입력이 가리킬 에러 메시지 id. */
  errorMessageId?: string;
  /** 바깥 라벨(`<label htmlFor>`)이 가리킬 id — 트리거 버튼에 단다. */
  id?: string;
  /** 도움말 문단 id. 검증 오류가 있으면 그쪽이 이긴다. */
  "aria-describedby"?: string;
  onChange: (next: any) => void;
}

/** 항목에서 값/표시를 뽑는다. 문자열 배열이면 항목 자체가 값이자 표시다. */
function readValue(item: any, valueExpr: string): any {
  return item !== null && typeof item === "object" ? item[valueExpr] : item;
}
function readLabel(item: any, displayExpr: string): string {
  if (item === null || item === undefined) return "";
  return item !== null && typeof item === "object" ? String(item[displayExpr] ?? "") : String(item);
}

export function SelectMenu({
  items,
  displayExpr,
  valueExpr,
  value,
  multiple = false,
  placeholder,
  readOnly = false,
  disabled = false,
  searchEnabled = false,
  acceptCustomValue = false,
  noDataText = "데이터가 없습니다",
  showClearButton,
  maxDisplayedTags,
  showSelectionControls = false,
  width,
  height,
  itemRender,
  fieldRender,
  isInvalid = false,
  id,
  "aria-describedby": describedBy,
  errorMessageId,
  onChange,
}: SelectMenuProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const listId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  //  **포털은 테마 선언 밖으로 나간다.** Radix Portal 의 기본 컨테이너가 `document.body` 라,
  //  `[data-theme="light"]` 를 셸 `<div>` 에 걸어 둔 `/admin` 에서 이 목록만 `:root`(다크)로
  //  풀린다. 컨테이너를 셸 안으로 옮기면 조상의 `overflow` 에 잘릴 위험이 생기므로, **연 자리의
  //  테마를 읽어 콘텐츠에 그대로 찍는다.** 없으면 안 찍고 `:root` 기본을 따른다.
  //  다이얼로그 안에서 열릴 때도 이 한 줄이 답을 낸다 — 다이얼로그 박스가 자기 모드를 선언하므로
  //  (primitives/dialog.tsx) 포털 안의 앵커가 `closest` 로 그 선언을 찾는다.
  const [openedTheme, setOpenedTheme] = useState<string | null>(null);
  const optionRefs = useRef<Array<HTMLLIElement | null>>([]);

  const selectedValues: any[] = multiple ? (Array.isArray(value) ? value : []) : [];
  const canSearch = searchEnabled || acceptCustomValue;

  const visibleItems = useMemo(() => {
    if (!canSearch || !search.trim()) return items;
    const needle = search.trim().toLowerCase();
    return items.filter((item) => readLabel(item, displayExpr).toLowerCase().includes(needle));
  }, [items, search, canSearch, displayExpr]);

  // 목록이 바뀌면 강조 위치가 범위를 벗어날 수 있다 — 앞으로 되감는다.
  useEffect(() => {
    setActiveIndex(0);
  }, [search, open]);

  useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  // 강조된 항목이 팝업 밖으로 나가면 스크롤로 따라간다(키보드 순회 시 항상 보이게).
  // `scrollIntoView` 는 레이아웃이 있는 환경에만 있다 — jsdom 에는 없어서 선택 호출로 둔다
  // (없다고 선택 동작이 달라지지 않는 순수 시각 보조다).
  useEffect(() => {
    optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex, open]);

  const labelFor = (targetValue: any): string => {
    const found = items.find((item) => readValue(item, valueExpr) === targetValue);
    return found === undefined ? String(targetValue ?? "") : readLabel(found, displayExpr);
  };
  const itemFor = (targetValue: any) => items.find((item) => readValue(item, valueExpr) === targetValue);

  const commit = (targetValue: any) => {
    if (!multiple) {
      onChange(targetValue);
      setOpen(false);
      return;
    }
    const next = selectedValues.includes(targetValue)
      ? selectedValues.filter((existing) => existing !== targetValue)
      : [...selectedValues, targetValue];
    onChange(next);
  };

  const commitCustomValue = () => {
    const text = search.trim();
    if (!acceptCustomValue || !text) return;
    // 목록에 이미 있으면 그 항목의 값을 쓴다 — 같은 표시로 두 값이 생기지 않게.
    const existing = items.find((item) => readLabel(item, displayExpr) === text);
    commit(existing ? readValue(existing, valueExpr) : text);
    setSearch("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, visibleItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(Math.max(0, visibleItems.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const active = visibleItems[activeIndex];
      if (active !== undefined) commit(readValue(active, valueExpr));
      else commitCustomValue();
    }
  };

  const hasValue = multiple ? selectedValues.length > 0 : value !== null && value !== undefined && value !== "";
  const clearVisible = (showClearButton ?? !readOnly) && hasValue && !readOnly && !disabled;

  // ── 닫힌 상태의 표시 ─────────────────────────────────────────────────────
  const renderTriggerContent = () => {
    // placeholder 도 읽는 글자다 — gray-400 은 다크에서 2.54:1 로 AA 미달이었다 (#203 실측).
    if (!hasValue) return <span className="truncate text-ink-muted">{placeholder}</span>;
    if (!multiple) {
      const selectedItem = itemFor(value);
      if (fieldRender && selectedItem !== undefined)
        return <span className="truncate">{fieldRender(selectedItem)}</span>;
      return <span className="truncate">{labelFor(value)}</span>;
    }
    const shown =
      maxDisplayedTags && selectedValues.length > maxDisplayedTags
        ? selectedValues.slice(0, maxDisplayedTags)
        : selectedValues;
    const hiddenCount = selectedValues.length - shown.length;
    return (
      <span className="flex min-w-0 flex-wrap items-center gap-1">
        {shown.map((entry) => (
          <span
            key={String(entry)}
            className="inline-flex max-w-full items-center gap-1 rounded bg-bg-raised px-1.5 py-0.5"
          >
            <span className="truncate">{labelFor(entry)}</span>
            {!readOnly && !disabled && (
              <button
                type="button"
                aria-label={`${labelFor(entry)} 제거`}
                className={cn(ICON_HIT_AREA, "text-ink-muted hover:text-ink")}
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(selectedValues.filter((existing) => existing !== entry));
                }}
              >
                ×
              </button>
            )}
          </span>
        ))}
        {hiddenCount > 0 && <span className="text-ink-muted">+{hiddenCount}</span>}
      </span>
    );
  };

  return (
    <PopoverPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (readOnly || disabled) return;
        if (next) setOpenedTheme(anchorRef.current?.closest("[data-theme]")?.getAttribute("data-theme") ?? null);
        setOpen(next);
      }}
    >
      <div ref={anchorRef} className="relative w-full" style={{ width }}>
        <PopoverPrimitive.Trigger asChild>
          <button
            type="button"
            id={id}
            disabled={disabled}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-invalid={isInvalid || undefined}
            aria-describedby={isInvalid && errorMessageId ? errorMessageId : describedBy}
            aria-readonly={readOnly || undefined}
            style={{ height }}
            className={cn(
              // 포커스 표시는 globals.css 의 `:focus-visible` outline 한 자리가 정본이다.
              "flex w-full items-center justify-between gap-1 rounded border px-3 py-1.5 text-left text-sm text-ink",
              "disabled:cursor-not-allowed disabled:bg-bg-raised disabled:text-ink-muted",
              readOnly ? "cursor-default bg-bg-raised" : "cursor-pointer bg-bg-panel",
              isInvalid ? "border-danger" : "border-line",
              clearVisible ? "pr-12" : "",
            )}
          >
            {renderTriggerContent()}
            <span aria-hidden="true" className="shrink-0 text-ink-muted">
              ▾
            </span>
          </button>
        </PopoverPrimitive.Trigger>

        {clearVisible && (
          <button
            type="button"
            aria-label="선택 지우기"
            // right-5 는 24 폭 상자를 트리거가 비워 둔 자리(`pr-12`) 안에 넣으면서 × 의 가운데를
            // 종전 자리에 유지한다 — 상자는 오른쪽 20~44px, ▾ 는 49~56px 이라 겹치지 않는다.
            className={cn(ICON_HIT_AREA, "absolute right-5 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink")}
            onClick={() => onChange(multiple ? [] : null)}
          >
            ×
          </button>
        )}
      </div>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          data-theme={openedTheme ?? undefined}
          align="start"
          sideOffset={4}
          className="z-[1100] max-h-64 w-[var(--radix-popover-trigger-width)] overflow-auto rounded border border-line bg-bg-panel py-1 text-sm text-ink shadow-lg motion-safe:data-[state=open]:animate-dialog-fade-in motion-safe:data-[state=closed]:animate-dialog-fade-out"
          onOpenAutoFocus={(e) => {
            // 검색이 있으면 입력으로, 없으면 목록으로 포커스를 옮긴다(Radix 기본 대상은 첫
            // 포커스 가능 요소라 항목 버튼으로 튀어 검색을 못 치는 경우가 생긴다).
            e.preventDefault();
            searchRef.current?.focus();
          }}
        >
          {canSearch && (
            <div className="px-2 pb-1">
              <input
                ref={searchRef}
                type="search"
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={visibleItems.length > 0 ? `${listId}-opt-${activeIndex}` : undefined}
                aria-label={acceptCustomValue ? "검색 또는 직접 입력" : "검색"}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleKeyDown}
                // 팝오버 안이라도 **자기 바탕을 칠한다** — 안 칠하면 브라우저 기본으로 떨어져
                // 팝오버(`--bg-panel`)와 다른 색이 된다. #281 이 고친 그 형태다.
                // 팝오버가 `--bg-panel` 이라 입력칸은 한 단 아래(`--bg-base`)를 써 파인 자리로 읽힌다.
                className="w-full rounded border border-line bg-bg-base px-2 py-1 text-sm text-ink placeholder:text-ink-muted"
              />
            </div>
          )}

          <ul
            id={listId}
            role="listbox"
            aria-multiselectable={multiple || undefined}
            tabIndex={canSearch ? -1 : 0}
            onKeyDown={canSearch ? undefined : handleKeyDown}
            ref={(node) => {
              // 검색이 없으면 목록 자체가 포커스를 받는다(위 onOpenAutoFocus 의 대체 대상).
              if (node && open && !canSearch) node.focus();
            }}
            className="focus:outline-none"
          >
            {visibleItems.length === 0 && <li className="px-3 py-2 text-ink-muted">{noDataText}</li>}
            {visibleItems.map((item, index) => {
              const itemValue = readValue(item, valueExpr);
              const isSelected = multiple ? selectedValues.includes(itemValue) : itemValue === value;
              return (
                <li
                  key={String(itemValue)}
                  id={`${listId}-opt-${index}`}
                  ref={(node) => {
                    optionRefs.current[index] = node;
                  }}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => commit(itemValue)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 px-3 py-1.5",
                    // 목록이 `focus:outline-none` 으로 정본 outline 을 눌러 두므로, 키보드 위치는
                    // **이 표시 하나뿐**이다. 바탕만으로는 `--bg-raised` on `--bg-panel` 1.35:1 이라
                    // 눈에 안 띈다 — 비텍스트 3:1 을 넘는 선(`--ink-muted`)을 함께 두른다.
                    index === activeIndex ? "bg-bg-raised ring-1 ring-inset ring-ink-muted" : "",
                    isSelected ? "font-medium text-ink-strong" : "text-ink",
                  )}
                >
                  {showSelectionControls && (
                    <input type="checkbox" readOnly checked={isSelected} tabIndex={-1} className="h-4 w-4" />
                  )}
                  {itemRender ? itemRender(item) : readLabel(item, displayExpr)}
                  {/* 선택 표시를 색·굵기로만 하지 않는다 — 체크 문자를 함께 둔다. */}
                  {isSelected && !showSelectionControls && (
                    <span aria-hidden="true" className="ml-auto">
                      ✓
                    </span>
                  )}
                </li>
              );
            })}
          </ul>

          {acceptCustomValue && search.trim() && (
            <button
              type="button"
              onClick={commitCustomValue}
              // 이건 목록 항목이 아니라 **동작**이다. 선택된 항목도 `--ink-strong` 을 쓰므로
              // 글자색만으로는 안 갈린다 — 구분선과 `+` 로 가른다(색에만 기대지 않는다).
              className="flex w-full items-center gap-1.5 border-t border-line px-3 py-1.5 text-left text-ink-strong hover:bg-bg-raised"
            >
              <span aria-hidden="true">+</span>
              &ldquo;{search.trim()}&rdquo; 추가
            </button>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
