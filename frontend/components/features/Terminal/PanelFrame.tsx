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
    <div className="flex h-full flex-col overflow-hidden border border-line bg-bg-panel">
      <div className="group flex flex-shrink-0 items-center justify-between gap-2 border-b border-line px-2 py-1 font-mono text-xs">
        <span className="min-w-0 flex-1 truncate text-ink">{definition.title}</span>
        {/*
          이 묶음은 **줄어들 수 있어야 한다.** 패널이 좁아지면(사이드바가 자리를 다 먹는 폭에서
          72px 까지 간다 — #289 실측) `flex-shrink-0` 인 묶음은 폭을 안 내주고 패널 상자 밖으로
          밀려나는데, 패널 뿌리가 `overflow-hidden` 이라 밀려난 부분은 **잘려서 못 누른다**.
          크기가 24 여도 그 좌표를 히트 테스트하면 버튼이 아니라 뒤엣것이 잡힌다.
          그래서 줄어드는 것은 출처 배지 쪽이고, `⋮` 만 `flex-shrink-0` 으로 자리를 지킨다.
        */}
        <div className="flex min-w-0 items-center gap-2">
          {/* `h-4` 는 이 줄의 글줄 높이(text-xs = 16px)다 — 좁아진 배지가 여러 줄로 접히면서
              패널 머리를 늘리는 것을 막는다(실측: 폭 390 에서 25px → 137px). 넘치는 부분은
              잘린다: 배지는 줄어들 수 있는 쪽이고 `⋮` 는 자리를 지키는 쪽이다. */}
          <span className="flex h-4 min-w-0 overflow-hidden">
            <ProvenanceBadge provenance={provenance} />
          </span>
          <div className="flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none">
            <PanelMenu collapsed={instance.collapsed} onToggleCollapse={onToggleCollapse} onClose={onClose} />
          </div>
        </div>
      </div>

      {/* 왜 임시인지와 무엇을 하면 진짜 값이 오는지 — 헤더 배지에 넣으면 제목을 밀어내므로
          (실측) 폭 전체를 쓰는 안내줄로 낸다. 접힌 패널에서는 본문과 함께 감춘다. */}
      {isPlaceholder && provenance.hint && !instance.collapsed && (
        <p className="flex-shrink-0 border-b border-line px-2 py-1 font-mono text-2xs leading-relaxed text-ink-muted">
          {provenance.hint}
        </p>
      )}

      {instance.collapsed ? (
        <div className="flex flex-1 items-center justify-center text-xs text-ink-muted">패널이 접혀 있습니다</div>
      ) : (
        <div className="relative flex-1 overflow-auto">
          {isUnavailable && <PanelUnavailable reason={provenance.reason} />}
          {/*
            사유가 떠 있어도 **자식은 트리에 남긴다.** 언마운트하면 그 사유를 갱신할 수 있는
            유일한 주체(자기 provenance 를 올리는 패널 자신)가 사라져, 한 번 unavailable 을
            올린 패널은 문맥이 바뀌어도 영영 그 사유에 갇힌다 — 구조적 교착이다
            (`SymbolInfoPanel` 의 긴 주석이 그 교착을 우회하려고 남아 있다).
            `contents` 는 이 래퍼가 레이아웃에 끼어들지 않게 한다.
          */}
          <div className={isUnavailable ? "hidden" : "contents"}>{children}</div>
          {isPlaceholder && (
            <div className="terminal-placeholder-hatch pointer-events-none absolute inset-0" aria-hidden="true" />
          )}
        </div>
      )}
    </div>
  );
}
