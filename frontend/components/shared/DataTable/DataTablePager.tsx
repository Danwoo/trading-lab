// components/shared/DataTable/DataTablePager.tsx
"use client";

import { ALLOWED_PAGE_SIZES } from "@/constants/app";

interface DataTablePagerProps {
  pageIndex: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (index: number) => void;
  onPageSizeChange: (size: number) => void;
}

const NAV_BUTTON_CLASS =
  "rounded border px-2 py-0.5 text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40";

export function DataTablePager({
  pageIndex,
  pageSize,
  totalCount,
  onPageChange,
  onPageSizeChange,
}: DataTablePagerProps) {
  const pageCount = Math.max(1, Math.ceil(totalCount / pageSize));
  const currentPage = Math.min(pageIndex, pageCount - 1);
  const isFirst = currentPage <= 0;
  const isLast = currentPage >= pageCount - 1;

  return (
    <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-3 border-t bg-white px-3 py-2 text-sm text-gray-600">
      <span aria-live="polite">총 {totalCount.toLocaleString()}건</span>

      <nav className="flex items-center gap-1" aria-label="페이지 이동">
        <button
          type="button"
          className={NAV_BUTTON_CLASS}
          onClick={() => onPageChange(0)}
          disabled={isFirst}
          aria-label="첫 페이지"
        >
          «
        </button>
        <button
          type="button"
          className={NAV_BUTTON_CLASS}
          onClick={() => onPageChange(currentPage - 1)}
          disabled={isFirst}
          aria-label="이전 페이지"
        >
          ‹
        </button>
        <span className="px-2" aria-live="polite">
          {currentPage + 1} / {pageCount}
        </span>
        <button
          type="button"
          className={NAV_BUTTON_CLASS}
          onClick={() => onPageChange(currentPage + 1)}
          disabled={isLast}
          aria-label="다음 페이지"
        >
          ›
        </button>
        <button
          type="button"
          className={NAV_BUTTON_CLASS}
          onClick={() => onPageChange(pageCount - 1)}
          disabled={isLast}
          aria-label="마지막 페이지"
        >
          »
        </button>
      </nav>

      <label className="flex items-center gap-1">
        <span>페이지당</span>
        <select
          className="rounded border px-1 py-0.5"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          aria-label="페이지당 표시 개수"
        >
          {ALLOWED_PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size}건
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
