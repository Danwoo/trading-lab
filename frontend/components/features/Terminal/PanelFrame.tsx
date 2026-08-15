import type * as React from "react";
import type { PanelDefinition } from "@/types/terminal/panel";
import type { PanelInstance } from "@/types/terminal/layout";
import type { Provenance } from "@/types/terminal/provenance";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { PanelMenu } from "./PanelMenu";
import { PanelUnavailable } from "./PanelUnavailable";

export interface PanelFrameProps {
  instance: PanelInstance;
  definition: PanelDefinition;
  provenance: Provenance | null;
  onToggleCollapse: () => void;
  onClose: () => void;
  children: React.ReactNode;
}

/**
 * 패널 하나의 틀 — 접힘·닫기 chrome 과 출처 표시를 소유한다 (설계 §3.5·§4).
 * 헤더는 제목 바가 아니라 모노 기록 한 줄이다. 조작은 포커스/호버 시 줄 끝에 나타난다 —
 * 쉬는 상태는 순수 정보다. 키보드 도달은 `PanelMenu`(항상 tab 순서에 있음)가 보장한다.
 */
export function PanelFrame({ instance, definition, provenance, onToggleCollapse, onClose, children }: PanelFrameProps) {
  const isUnavailable = provenance?.kind === "unavailable";
  const isPlaceholder = provenance?.kind === "placeholder";

  return (
    <div className="flex h-full flex-col overflow-hidden border border-slate-line bg-slate-panel">
      <div className="group flex flex-shrink-0 items-center justify-between gap-2 border-b border-slate-line px-2 py-1 font-mono text-xs">
        <span className="min-w-0 flex-1 truncate text-ink-primary">{definition.title}</span>
        <div className="flex flex-shrink-0 items-center gap-2">
          <ProvenanceBadge provenance={provenance} />
          <div className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none">
            <PanelMenu collapsed={instance.collapsed} onToggleCollapse={onToggleCollapse} onClose={onClose} />
          </div>
        </div>
      </div>

      {instance.collapsed ? (
        <div className="flex flex-1 items-center justify-center text-xs text-ink-muted">패널이 접혀 있습니다</div>
      ) : isUnavailable ? (
        <PanelUnavailable reason={provenance.reason} />
      ) : (
        <div className="relative flex-1 overflow-auto">
          {children}
          {isPlaceholder && (
            <div className="terminal-placeholder-hatch pointer-events-none absolute inset-0" aria-hidden="true" />
          )}
        </div>
      )}
    </div>
  );
}
