"use client";

import { useState } from "react";
import { ResearchSource } from "@/schemas/researchChat/researchChat";

// 처음 보이는 근거 수 — 초과분은 disclosure 버튼으로 펼침.
const INITIAL_VISIBLE = 3;

interface Props {
  sources: ResearchSource[];
}

// 문서 아이콘 — 업로드 리서치 문서(url 없음, 비클릭).
function DocumentIcon() {
  return (
    <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.6}
        d="M9 12h6m-6 4h6m2 4H7a2 2 0 01-2-2V6a2 2 0 012-2h5.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V18a2 2 0 01-2 2z"
      />
    </svg>
  );
}

// 외부 링크 아이콘 — 웹/뉴스/공시/시세(클릭 가능).
function ExternalLinkIcon() {
  return (
    <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.6}
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  );
}

/**
 * 근거 카드 1건. url 유무로 두 갈래 — 색이 아닌 아이콘 + 텍스트 라벨(domain)로 유형 구분(WCAG).
 * - url === "" : 업로드 리서치 문서(domain="사내 리서치자료", title=file_nm). 정적 카드(비클릭).
 * - url 존재   : 외부 소스. title 을 새 탭 링크로(rel="noopener noreferrer"), favicon 은 장식(alt="").
 */
function SourceItem({ source }: { source: ResearchSource }) {
  const isDocument = source.url === "";
  return (
    <li className="rounded-md border border-gray-200 bg-white p-2">
      <div className="flex gap-2">
        <span className="mt-0.5 flex-shrink-0">{isDocument ? <DocumentIcon /> : <ExternalLinkIcon />}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {!isDocument && source.favicon && (
              <img src={source.favicon} alt="" className="h-3.5 w-3.5 flex-shrink-0 rounded-sm" />
            )}
            <span className="truncate text-[11px] font-medium text-gray-500">{source.domain || "출처"}</span>
          </div>
          {isDocument ? (
            <div className="mt-0.5 text-sm font-medium text-gray-800">{source.title}</div>
          ) : (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 block text-sm font-medium text-blue-600 hover:underline"
            >
              {source.title}
            </a>
          )}
          {source.content && <p className="mt-0.5 line-clamp-2 text-xs text-gray-500">{source.content}</p>}
        </div>
      </div>
    </li>
  );
}

/**
 * assistant 답변의 근거(citation) 리스트. media.sources[] 를 시맨틱 리스트로 렌더.
 * 근거가 INITIAL_VISIBLE 을 넘으면 disclosure 버튼(aria-expanded)으로 접는다 —
 * ExpandableCard 대신 disclosure 를 쓰는 이유는 아래 링크 카드와의 nested-interactive 충돌 회피.
 */
export function SourceCards({ sources }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (sources.length === 0) return null;

  const hasMore = sources.length > INITIAL_VISIBLE;
  const visible = expanded ? sources : sources.slice(0, INITIAL_VISIBLE);

  return (
    <section aria-label={`근거 ${sources.length}건`} className="mt-3 border-t border-gray-200 pt-2">
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
        근거 {sources.length}건
      </div>
      <ul className="space-y-1.5">
        {visible.map((source, index) => (
          <SourceItem key={`${source.url || source.title}-${index}`} source={source} />
        ))}
      </ul>
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-1.5 text-xs font-medium text-blue-600 hover:underline"
        >
          {expanded ? "근거 접기" : `근거 ${sources.length - INITIAL_VISIBLE}건 더 보기`}
        </button>
      )}
    </section>
  );
}
