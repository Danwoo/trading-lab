"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { cn } from "@/components/shared/ui/primitives/cn";
import { useViewportBand } from "@/hooks/shared/useViewportBand";
import { useBenchSelectionStore, type BenchSelectionKind } from "@/stores/shell/benchSelectionStore";

/**
 * 보드에 상시로 있는 넷 (§20.2). 격자·곡선은 백테스트·봇 엔진 산출물이라 마일스톤 2 의
 * no-go 이고, 빈 상태(§21.4)는 S4 의 몫이다 — 여기서는 **무엇이 올 자리인지**만 적는다.
 *
 * `marks` 는 §20.2 「패널에서 고르기 = 보드가 그 지점 표시」에서 이 자리가 받는 선택 종류다.
 */
const BOARD_ZONES = [
  {
    id: "grid",
    title: "격자",
    note: "파라미터 조합 100가지. 칸을 누르면 곡선이 바뀝니다.",
    marks: "grid-point" as BenchSelectionKind,
  },
  {
    id: "curve",
    title: "곡선",
    note: "자산 추이 + 구간 브러시. 구간을 끌면 그 구간만 다시 계산합니다.",
    marks: "curve-point" as BenchSelectionKind,
  },
  { id: "bots", title: "내 봇", note: "만든 봇 목록과 지금 상태.", marks: "bot" as BenchSelectionKind },
  { id: "today", title: "오늘 할 일", note: "어젯밤에 한 일 · 정해야 할 것.", marks: null },
] as const;

/** 좁은 화면에서 하나씩 보여주는 둘 (§21.6 「보드가 먼저 양보한다」) */
const TABBED_ZONE_IDS = ["grid", "curve"] as const;
type TabbedZoneId = (typeof TABBED_ZONE_IDS)[number];

function Zone({ zone }: { zone: (typeof BOARD_ZONES)[number] }) {
  const selection = useBenchSelectionStore((s) => s.selection);
  const marked = zone.marks !== null && selection?.kind === zone.marks;

  return (
    <section
      aria-label={zone.title}
      className={cn(
        "rounded border border-dashed border-slate-line bg-slate-panel p-4",
        marked && "border-solid border-ink-muted",
      )}
    >
      <h2 className="text-sm font-medium text-ink-primary">{zone.title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{zone.note}</p>
      {marked && selection && (
        <p className="mt-2 text-sm text-ink-muted">
          <span className="text-ink-primary">{selection.label}</span>
          {selection.origin === "panel" ? " — 패널에서 고른 지점을 여기 표시합니다." : " — 이 지점을 골랐습니다."}
        </p>
      )}
    </section>
  );
}

/**
 * 실험대 — 제품의 홈 (화면 결정 §20.2 「㉮ 실험대가 홈」).
 *
 * 1280 미만에서 격자·곡선을 **탭으로 하나씩** 내놓는다(§21.6) — 나란히 두면 둘 다 못 읽고,
 * 양보하는 쪽은 패널이 아니라 보드다. 내 봇·오늘 할 일은 접지 않는다(읽는 데 폭이 덜 든다).
 */
export default function Page() {
  const band = useViewportBand();
  const [activeTab, setActiveTab] = useState<TabbedZoneId>("grid");
  const tabRefs = useRef(new Map<TabbedZoneId, HTMLButtonElement>());

  const zoneById = (id: string) => BOARD_ZONES.find((zone) => zone.id === id)!;
  const restZones = BOARD_ZONES.filter((zone) => !TABBED_ZONE_IDS.includes(zone.id as TabbedZoneId));

  const handleTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const index = TABBED_ZONE_IDS.indexOf(activeTab);
    const next = TABBED_ZONE_IDS[(index + step + TABBED_ZONE_IDS.length) % TABBED_ZONE_IDS.length];
    setActiveTab(next);
    tabRefs.current.get(next)?.focus();
  };

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header>
        <h1 className="text-lg font-medium text-ink-primary">실험대</h1>
        <p className="mt-1 text-sm text-ink-muted">
          봇을 만들고 검증하고 굴리는 자리입니다. 아래 넷이 이 화면에 상시로 놓입니다.
        </p>
      </header>

      {band === "wide" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {TABBED_ZONE_IDS.map((id) => (
            <Zone key={id} zone={zoneById(id)} />
          ))}
        </div>
      ) : (
        <div>
          <div role="tablist" aria-label="보드 보기" onKeyDown={handleTabKeyDown} className="flex gap-1">
            {TABBED_ZONE_IDS.map((id) => (
              <button
                key={id}
                ref={(el) => {
                  if (el) tabRefs.current.set(id, el);
                  else tabRefs.current.delete(id);
                }}
                type="button"
                role="tab"
                id={`board-tab-${id}`}
                aria-selected={activeTab === id}
                aria-controls={`board-panel-${id}`}
                tabIndex={activeTab === id ? 0 : -1}
                onClick={() => setActiveTab(id)}
                className={cn(
                  "rounded-t border-b-2 px-3 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
                  activeTab === id ? "border-ink-primary text-ink-primary" : "border-transparent text-ink-muted",
                )}
              >
                {zoneById(id).title}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id={`board-panel-${activeTab}`}
            aria-labelledby={`board-tab-${activeTab}`}
            className="mt-2"
          >
            <Zone zone={zoneById(activeTab)} />
          </div>
        </div>
      )}

      <div className="grid min-h-0 flex-1 gap-3 sm:grid-cols-2">
        {restZones.map((zone) => (
          <Zone key={zone.id} zone={zone} />
        ))}
      </div>
    </div>
  );
}
