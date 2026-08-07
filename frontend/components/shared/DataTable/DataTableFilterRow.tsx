// components/shared/DataTable/DataTableFilterRow.tsx
"use client";

import { type CSSProperties, useEffect, useRef, useState } from "react";
import type { GridColumn, GridLookup } from "@/types/grid";
import { type ColumnLayoutMap, STICKY_SHADOW_CLASS, type StickyPlacement } from "./gridColumnLayout";

interface DataTableFilterRowProps<T> {
  columns: GridColumn<T>[];
  filter: unknown[] | undefined;
  onFilterChange: (filter: unknown[] | undefined) => void;
  columnLayout: ColumnLayoutMap;
}

function stickyCellStyle(placement: StickyPlacement | undefined): CSSProperties {
  if (!placement) return {};
  return {
    position: "sticky",
    [placement.position]: placement.offset,
    zIndex: 20,
  };
}

const FILTER_DEBOUNCE_MS = 400;

// 텍스트 컬럼은 contains, 숫자·날짜·룩업(코드 컬럼)은 정확일치 — 두 파서(파이썬·TS) 가 공통으로
// 지원하는 18종 중 이 두 연산자만 쓴다. between·in·isblank 등 나머지는 2단계 이후 판단
// (#242 O1 착수 코멘트). 룩업 컬럼은 표시값이 아니라 raw 코드에 거는 것이므로 "=" 가 맞다 —
// "사용"을 contains 로 걸면 코드 "Y" 에 부분일치가 안 된다(#321).
function operatorFor<T>(col: GridColumn<T>): string {
  if (col.lookup) return "=";
  return col.dataType === "number" || col.dataType === "date" || col.dataType === "datetime" ? "=" : "contains";
}

function coerceValue<T>(raw: string, col: GridColumn<T>): unknown {
  // 룩업 값은 select 가 이미 valueField 원값(대개 문자열 코드)을 그대로 준다 — 숫자 변환을
  // 거치면 "01" 같은 코드가 1로 바뀌어 서버 비교가 어긋날 수 있다.
  if (col.lookup) return raw;
  if (col.dataType !== "number") return raw;
  const num = Number(raw);
  return Number.isNaN(num) ? raw : num;
}

function buildFilter<T>(columns: GridColumn<T>[], values: Record<string, string>): unknown[] | undefined {
  const conditions = columns
    .filter((col) => col.filterable !== false && values[col.field]?.trim())
    .map((col) => [col.field, operatorFor(col), coerceValue(values[col.field].trim(), col)]);

  if (conditions.length === 0) return undefined;
  if (conditions.length === 1) return conditions[0];

  const grouped: unknown[] = [];
  conditions.forEach((condition, index) => {
    if (index > 0) grouped.push("and");
    grouped.push(condition);
  });
  return grouped;
}

/** `GridLookup.items` 는 임의 형태(`unknown[]`)라 valueField/displayField 로 안전하게 뽑는다. */
function lookupOptions(lookup: GridLookup): Array<{ value: string; label: string }> {
  return lookup.items.map((item) => {
    const record = item as Record<string, unknown>;
    return {
      value: String(record[lookup.valueField] ?? ""),
      label: String(record[lookup.displayField] ?? ""),
    };
  });
}

/** 헤더 아래 컬럼별 텍스트 필터 입력 — `<tr>` 안에 들어갈 `<td>` 들만 반환한다(선택 열 정렬은 DataTable 이 맡는다). */
export function DataTableFilterRow<T>({ columns, filter, onFilterChange, columnLayout }: DataTableFilterRowProps<T>) {
  const [values, setValues] = useState<Record<string, string>>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (filter === undefined) setValues({});
  }, [filter]);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const handleChange = (field: string, raw: string) => {
    const next = { ...values, [field]: raw };
    setValues(next);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onFilterChange(buildFilter(columns, next)), FILTER_DEBOUNCE_MS);
  };

  // 룩업(select)은 자유 타이핑이 아니라 이산 선택이다 — 타이핑 debounce 를 거칠 이유가 없고,
  // 오히려 선택 직후 반응이 늦어 보인다. 대기 중인 텍스트 필터 타이머와 섞이지 않도록 즉시 반영한다.
  const handleLookupChange = (field: string, raw: string) => {
    const next = { ...values, [field]: raw };
    setValues(next);
    if (timerRef.current) clearTimeout(timerRef.current);
    onFilterChange(buildFilter(columns, next));
  };

  return (
    <>
      {columns.map((col) => {
        const sticky = columnLayout[col.field]?.sticky;
        // 필터 행도 헤더·바디와 같은 sticky 오프셋을 써야 가로 스크롤 시 세 행(헤더·필터·
        // 데이터)의 고정 컬럼 경계가 어긋나지 않는다.
        const className = `px-2 py-1 ${sticky ? `bg-gray-50 ${sticky.isBoundary ? STICKY_SHADOW_CLASS[sticky.position] : ""}` : ""}`;
        const style = stickyCellStyle(sticky);

        if (col.filterable === false) return <td key={col.field} className={className} style={style} />;

        return (
          <td key={col.field} className={className} style={style}>
            {col.lookup ? (
              // 화면엔 표시명(공통코드 이름)이 보이는데 필터가 raw 코드 자유텍스트만 받으면
              // "사용"·"높음" 을 타이핑해도 0건이 나온다(#321) — 드롭다운으로 표시명을 고르게
              // 하고, 실제로 나가는 값은 lookup.valueField 원값이다.
              <select
                value={values[col.field] ?? ""}
                onChange={(event) => handleLookupChange(col.field, event.target.value)}
                aria-label={`${col.caption} 필터`}
                className="w-full rounded border px-1.5 py-0.5 text-xs"
              >
                <option value="">전체</option>
                {lookupOptions(col.lookup).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={values[col.field] ?? ""}
                onChange={(event) => handleChange(col.field, event.target.value)}
                placeholder={`${col.caption} 검색`}
                aria-label={`${col.caption} 필터`}
                className="w-full rounded border px-1.5 py-0.5 text-xs"
              />
            )}
          </td>
        );
      })}
    </>
  );
}
