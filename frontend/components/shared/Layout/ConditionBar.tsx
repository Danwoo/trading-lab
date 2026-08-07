// components/shared/Layout/ConditionBar.tsx
"use client";

import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { SelectBox } from "@/components/shared/ui";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";

interface Props {
  /** 내장 1차 스코프 select (옵션) — fetchItems 가 있을 때만 렌더 */
  label?: string;
  value?: number | string | null;
  onChange?: (value: any) => void;
  /** 옵션 로더 — { items } 반환. 객체 배열(+displayExpr/valueExpr) · 문자열 배열 모두 허용 */
  fetchItems?: () => Promise<{ items: any[] } | null>;
  displayExpr?: string;
  valueExpr?: string;
  placeholder?: string;
  width?: number;
  searchEnabled?: boolean;
  /** 로드된 항목 콜백 (부모가 목록 자체를 필요로 할 때) */
  onItemsLoaded?: (items: any[]) => void;
  /** 추가 조건 컨트롤 (날짜범위·상태필터 등) */
  children?: ReactNode;
}

/**
 * 목록/작업영역 상단 조건 바 — 내장 스코프 select(옵션) + 임의 조건 컨트롤(children).
 * fetchItems 지정 시 라벨+검색 드롭다운을 자체 로딩, 그 외 조건은 children 으로 조합한다.
 */
export function ConditionBar({
  label,
  value,
  onChange,
  fetchItems,
  displayExpr,
  valueExpr,
  placeholder,
  width = 300,
  searchEnabled = true,
  onItemsLoaded,
  children,
}: Props) {
  const [items, setItems] = useState<any[]>([]);

  // 콜백/로더를 ref 로 고정 — 인라인으로 와도 재로드 루프 방지
  const fetchRef = useRef(fetchItems);
  const onItemsLoadedRef = useRef(onItemsLoaded);
  useEffect(() => {
    fetchRef.current = fetchItems;
    onItemsLoadedRef.current = onItemsLoaded;
  });

  const load = useCallback(async () => {
    if (!fetchRef.current) return;
    try {
      const result = await fetchRef.current();
      if (result?.items) {
        setItems(result.items);
        onItemsLoadedRef.current?.(result.items);
      }
    } catch (error) {
      showToast(getApiErrorMessage(error), "error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex-shrink-0 p-3 bg-gray-50 border-b">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        {fetchItems && (
          <div className="flex items-center gap-2">
            {label && <span className="font-medium text-sm">{label}</span>}
            <SelectBox
              fieldName="scope"
              value={value ?? null}
              items={items}
              displayExpr={displayExpr}
              valueExpr={valueExpr}
              placeholder={placeholder}
              searchEnabled={searchEnabled}
              showClearButton
              width={width}
              onValueChanged={(_f, v) => onChange?.(v)}
            />
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
