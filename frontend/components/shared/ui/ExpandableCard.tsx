// components/shared/ui/ExpandableCard.tsx
"use client";

import React from "react";

interface Props {
  /** 펼침 여부 */
  isExpanded: boolean;
  /** 토글 핸들러 */
  onToggle: () => void;
  /** 좌측 영역 (썸네일/아이콘 등) — 옵션 */
  leading?: React.ReactNode;
  /** 우측 본문의 상단 헤더 (상태 dot + 제목 + 메타 배지). 펼침/접힘 모두에서 표시 */
  header: React.ReactNode;
  /** 접힘 상태에서 표시할 미리보기 — 옵션 */
  preview?: React.ReactNode;
  /** 펼침 상태에서 표시할 본문 */
  children?: React.ReactNode;
  /** 비활성/제외 등 흐림 처리 */
  muted?: boolean;
  /** 외곽 컨테이너 추가 클래스 */
  className?: string;
}

/**
 * 펼침/접힘이 가능한 카드.
 * - 행 전체 클릭 → 토글
 * - 우측 끝에 ▼/▲ 화살표 표시
 * - 청크/이미지 카드 등에 공용
 */
export function ExpandableCard({
  isExpanded,
  onToggle,
  leading,
  header,
  preview,
  children,
  muted,
  className = "",
}: Props) {
  return (
    <div
      className={`bg-white border border-gray-200 rounded cursor-pointer hover:border-gray-300 transition-colors ${muted ? "opacity-50" : ""} ${className}`}
      onClick={onToggle}
    >
      <div className="flex gap-3 p-2">
        {leading && <div className="flex-shrink-0">{leading}</div>}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">{header}</div>
            <span className="text-xs text-gray-400 flex-shrink-0 ml-2">{isExpanded ? "▲" : "▼"}</span>
          </div>
          {!isExpanded && preview !== undefined && <div className="mt-1">{preview}</div>}
          {isExpanded && children !== undefined && <div className="mt-1">{children}</div>}
        </div>
      </div>
    </div>
  );
}
