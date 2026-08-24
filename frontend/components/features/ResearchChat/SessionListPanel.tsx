"use client";

import { ResearchSession } from "@/schemas/researchChat/researchChat";
import { ICON_HIT_AREA } from "@/components/shared/ui/primitives/hitArea";

interface Props {
  sessions: ResearchSession[];
  activeGid: number | null;
  onSelect: (gid: number) => void;
  onNew: () => void;
  onDelete: (gid: number) => void;
}

/**
 * 좌측 세션 목록 패널 (프레젠테이션 — 상태 없음).
 * 새 대화 버튼 + 세션 리스트(선택/삭제). 활성 항목 aria-current="true".
 */
export function SessionListPanel({ sessions, activeGid, onSelect, onNew, onDelete }: Props) {
  return (
    <div className="flex h-full flex-col bg-gray-50">
      <div className="flex-shrink-0 p-2">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          새 대화
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-2 pb-2">
        {sessions.length === 0 ? (
          <div role="status" className="px-2 py-6 text-center text-xs text-gray-400">
            아직 대화가 없습니다.
            <br />
            &lsquo;새 대화&rsquo;로 시작하세요.
          </div>
        ) : (
          <ul className="space-y-1">
            {sessions.map((session) => {
              const isActive = session.gid === activeGid;
              return (
                <li key={session.gid} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(session.gid)}
                    aria-current={isActive ? "true" : undefined}
                    // 겹쳐 놓인 삭제 상자(`right-1`=4px + 표적 + 4 여유)만큼 제목이 비운다 — 값은
                    // 표적 토큰에서 파생한다(hitArea.ts 「겹쳐 놓는 자리」).
                    // `min-h-touch-icon` 은 그 상자를 줄 **안에** 가둔다: 줄이 36px 인데 표적이 44px
                    // 이면 `-translate-y-1/2` 로 위아래 4px 씩 새고, 그 띠가 줄 사이 여백(`space-y-1`)
                    // 을 덮어 옆 대화를 고르려던 손가락이 삭제를 누른다.
                    className={`min-h-touch-icon w-full truncate rounded-md py-2 pl-3 pr-[calc(var(--touch-icon-target)+8px)] text-left text-sm transition-colors ${
                      isActive ? "bg-blue-100 font-medium text-blue-800" : "text-gray-700 hover:bg-gray-100"
                    }`}
                    title={session.title || "새 대화"}
                  >
                    {session.title || "새 대화"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(session.gid)}
                    aria-label={`대화 삭제: ${session.title || "새 대화"}`}
                    title="대화 삭제"
                    // 호버가 없는 기기에서는 **처음부터 보인다.** `opacity: 0` 은 히트 테스트를 막지 않아,
                    // 그대로 두면 손가락 기기에서 「안 보이는데 눌리는 삭제 버튼」이 된다(확인 없이 지운다).
                    className={`${ICON_HIT_AREA} absolute right-1 top-1/2 -translate-y-1/2 rounded text-gray-400 opacity-0 transition-opacity hover:bg-gray-200 hover:text-gray-600 focus:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100`}
                  >
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
