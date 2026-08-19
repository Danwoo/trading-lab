"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import {
  BenchPaths,
  BoardZone,
  GridRunForm,
  ImpactNotice,
  ParamGrid,
  QuoteFreshnessBanner,
  RunReportView,
} from "@/components/features/Bench";
import { cn } from "@/components/shared/ui/primitives/cn";
import { useBacktestBoard } from "@/hooks/bench/useBacktestBoard";
import { useBotRoster } from "@/hooks/bench/useBotRoster";
import { useGridRunForm } from "@/hooks/bench/useGridRunForm";
import {
  useBenchSelectionStore,
  type BenchSelection,
  type BenchSelectionKind,
} from "@/stores/shell/benchSelectionStore";
import type { Provenance } from "@/types/terminal/provenance";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { ProductStages } from "@/components/features/Bench/ProductStages";

/** 좁은 화면에서 하나씩 보여주는 둘 (§21.6 「보드가 먼저 양보한다」) */
const TABBED_ZONE_IDS = ["grid", "curve"] as const;
type TabbedZoneId = (typeof TABBED_ZONE_IDS)[number];

const TAB_TITLES: Record<TabbedZoneId, string> = { grid: "격자", curve: "곡선" };

/**
 * 고른 지점을 자리 안에 적는다 — §20.2 「패널에서 고르기 = 보드가 그 지점 표시」.
 * 문구는 어느 쪽에서 골랐는지에 따라 갈린다.
 */
function SelectionLine({ selection, kind }: { selection: BenchSelection | null; kind: BenchSelectionKind }) {
  if (selection === null || selection.kind !== kind) return null;

  return (
    <p className="break-keep text-sm text-ink-muted">
      <span className="text-ink">{selection.label}</span>
      {selection.origin === "panel" ? " — 패널에서 고른 지점을 여기 표시합니다." : " — 이 지점을 골랐습니다."}
    </p>
  );
}

/**
 * 실험대 — 제품의 홈 (화면 결정 §20.2 「㉮ 실험대가 홈」).
 *
 * **빈 자리마다 무엇이 올 것인지 적고 길을 둘 준다**(§21.4). 그리고 데이터가 낡거나 없으면
 * 상단 띠가 그것을 말한다(§21.5) — 조용히 굴러가지 않는 것이 이 화면의 약속이다.
 *
 * 백테스트 엔진(#200~#202)이 붙어 격자·곡선이 **실제 산출물로 찬다**(#203) — 봇이 0개거나
 * 아직 안 돌렸으면 여전히 무엇이 올 자리인지 말한다. 채우는 것은 결과가 있을 때다.
 *
 * **폭 구간은 CSS 가 가른다.** 1280 이상은 격자·곡선이 나란히, 그 아래는 탭 하나씩(§21.6)인데
 * 그 판정을 JS 상태로 하면 서버 스냅샷과 실제 폭이 달라 첫 페인트가 튄다. 그래서 두 배치를
 * 다 두고 Tailwind 브레이크포인트(`xl` = 1280)가 하나만 보이게 한다 — 안 보이는 쪽은
 * `display:none` 이라 접근성 트리에서도 빠지므로, 어느 폭에서도 탭 의미가 어긋나지 않는다.
 */
export default function Page() {
  const [activeTab, setActiveTab] = useState<TabbedZoneId>("grid");
  const tabRefs = useRef(new Map<TabbedZoneId, HTMLButtonElement>());
  const selection = useBenchSelectionStore((s) => s.selection);
  const roster = useBotRoster();
  const board = useBacktestBoard();
  // 폼 상태는 페이지가 하나만 만든다 — 격자 자리가 두 배치에 두 벌 마운트돼도(§21.6) 입력은 하나다.
  const runForm = useGridRunForm();

  const bots = roster.data;
  const botCount = bots?.length ?? 0;
  const rosterUnreadable = roster.provenance.kind === "unavailable";

  const handleTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const index = TABBED_ZONE_IDS.indexOf(activeTab);
    const next = TABBED_ZONE_IDS[(index + step + TABBED_ZONE_IDS.length) % TABBED_ZONE_IDS.length];
    setActiveTab(next);
    tabRefs.current.get(next)?.focus();
  };

  // 격자에서 고른 칸 — 같은 칸을 다시 누르면 선택이 풀리므로(스토어 규칙) 리포트도 함께 접는다.
  const selectedRunId = selection?.kind === "grid-point" ? Number(selection.id) : null;
  const activeReport = board.report !== null && board.report.run.run_id === selectedRunId ? board.report : null;

  // 격자·곡선이 비어 있는 이유는 상태마다 다르다. 「봇이 없다」·「아직 안 돌렸다」·「칸을 아직
  // 안 골랐다」를 한 문장으로 뭉개면 사용자가 무엇을 하면 되는지가 사라진다.
  const gridProvenance: Provenance =
    board.grid !== null
      ? { kind: "loaded", source: "백테스트 격자", asOf: null }
      : {
          kind: "unavailable",
          reason:
            botCount === 0
              ? "돌릴 봇이 없습니다 — 봇을 하나 만들면 조합이 여기 깔립니다"
              : "아직 돌리지 않았습니다 — 봇·종목·구간을 골라 실행하면 조합이 칸으로 깔립니다",
        };

  const curveProvenance: Provenance = activeReport
    ? {
        kind: "loaded",
        source: `실행 #${activeReport.run.run_id}`,
        asOf: activeReport.run.finished_dt,
      }
    : {
        kind: "unavailable",
        reason: board.isReportLoading
          ? "리포트를 불러오고 있습니다"
          : (board.reportError ??
            (board.grid !== null
              ? "격자에서 칸을 누르면 그 조합의 곡선·지표·거래가 여기 그려집니다"
              : botCount === 0
                ? "거래가 0건이라 그릴 곡선이 없습니다"
                : "아직 돌리지 않았습니다 — 격자를 실행하면 곡선이 그려집니다")),
      };

  const rosterProvenance: Provenance =
    roster.isLoading && bots === null
      ? { kind: "unavailable", reason: "봇 목록을 확인하고 있습니다" }
      : botCount === 0 && !rosterUnreadable
        ? { kind: "unavailable", reason: "아직 만든 봇이 없습니다" }
        : roster.provenance;

  const gridZone = (
    <BoardZone
      title="격자"
      incoming="파라미터 조합이 칸으로 깔립니다. 칸을 누르면 곡선이 그 조합으로 바뀝니다."
      provenance={gridProvenance}
      marked={selection?.kind === "grid-point"}
    >
      <SelectionLine selection={selection} kind="grid-point" />
      {botCount > 0 && (
        <div className="flex min-w-0 flex-col gap-3">
          <GridRunForm
            bots={bots}
            controller={runForm}
            isRunning={board.isRunning}
            runError={board.runError}
            onRun={board.runGrid}
          />
          {board.grid !== null && (
            <ParamGrid grid={board.grid} selectedRunId={selectedRunId} onSelect={board.selectCell} />
          )}
        </div>
      )}
    </BoardZone>
  );

  const curveZone = (
    <BoardZone
      title="곡선"
      incoming="고른 조합의 자산 추이·낙폭과 판정 지표, 거래 목록."
      provenance={curveProvenance}
      marked={selection?.kind === "curve-point"}
    >
      <SelectionLine selection={selection} kind="curve-point" />
      {activeReport !== null && (
        <div className="flex min-w-0 flex-col gap-1">
          <RunReportView report={activeReport} />
          {board.lastReportMs !== null && (
            <p className="break-keep text-2xs text-ink-muted">
              칸 클릭 → 갱신 {board.lastReportMs}ms{board.lastReportMs === 0 ? " (캐시)" : ""} — 예산 500ms (스펙 §5)
            </p>
          )}
        </div>
      )}
    </BoardZone>
  );

  return (
    <div className="flex min-h-full min-w-0 flex-col gap-4 p-4 xl:p-6">
      <header className="min-w-0">
        <h1 className="break-keep text-base font-title text-ink-strong">실험대</h1>
        <p className="mt-1 break-keep text-sm text-ink-muted">
          봇을 만들고 조건을 다듬는 자리입니다. 아래 넷이 이 화면에 상시로 놓입니다.
          <br />
          검증(백테스트)과 굴리기(주문)는 아직 없습니다 — 무엇이 언제 오는지는 아래에 적어 두었습니다.
        </p>
      </header>

      <ProductStages />

      <QuoteFreshnessBanner />

      <section aria-label="시작하는 길" className="min-w-0">
        <p className="mb-2 break-keep text-sm text-ink">
          {botCount === 0
            ? "아직 봇이 없습니다. 두 갈래 중 하나로 시작하시면 됩니다."
            : `봇 ${botCount}개가 있습니다. 하나 더 만드시려면 여기서 시작하시면 됩니다.`}
        </p>
        <BenchPaths />
      </section>

      {/* 1280 이상 — 격자·곡선이 나란히 (§21.6) */}
      <div className="hidden gap-3 xl:grid xl:min-h-[50svh] xl:grid-cols-2">
        {gridZone}
        {curveZone}
      </div>

      {/* 1280 미만 — 격자 / 곡선 탭으로 하나씩 (§21.6) */}
      <div className="flex min-h-[50svh] min-w-0 flex-col xl:hidden">
        <div role="tablist" aria-label="보드 보기" onKeyDown={handleTabKeyDown} className="flex flex-wrap gap-1">
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
                "min-h-touch-min rounded-t border-b-2 px-3 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
                activeTab === id ? "border-ink text-ink" : "border-transparent text-ink-muted",
              )}
            >
              {TAB_TITLES[id]}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          id={`board-panel-${activeTab}`}
          aria-labelledby={`board-tab-${activeTab}`}
          className="mt-2 grid min-h-0 min-w-0 flex-1"
        >
          {activeTab === "grid" ? gridZone : curveZone}
        </div>
      </div>

      {/* 내 봇 · 오늘 할 일 — 어느 폭에서도 접지 않는다 (읽는 데 폭이 덜 든다) */}
      <div className="grid min-w-0 gap-3 lg:grid-cols-2">
        <BoardZone
          title="내 봇"
          incoming="만든 봇과 지금 상태."
          provenance={rosterProvenance}
          marked={selection?.kind === "bot"}
          notice={
            rosterUnreadable ? (
              <ImpactNotice
                headline="봇 목록을 읽지 못했습니다 — 「0개」인지 「못 읽었다」인지 모르는 상태입니다"
                halted={["내 봇 목록", "봇 수에 따른 안내"]}
                running={["봇 만들기", "시세 보기"]}
                detail={roster.error ? getApiErrorMessage(roster.error) : null}
              />
            ) : undefined
          }
        >
          <SelectionLine selection={selection} kind="bot" />
          {bots !== null && bots.length > 0 && (
            // 목록이 길어져도 이 자리가 보드를 밀어내지 않게 자기 상자 안에서 스크롤한다.
            // 높이는 뷰포트 비례라 화면이 커지면 더 많이 보인다.
            <ul className="flex max-h-[22svh] flex-col gap-1 overflow-y-auto">
              {bots.map((bot) => (
                <li key={bot.bot_id} className="flex min-w-0 flex-wrap items-baseline gap-x-2 text-sm">
                  <span className="min-w-0 break-keep text-ink">{bot.bot_nm}</span>
                  <span className="break-keep text-2xs text-ink-muted">
                    {bot.bot_role} · {bot.use_at === "Y" ? "사용" : "중지"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </BoardZone>

        <BoardZone
          title="오늘 할 일"
          incoming="어젯밤에 리서치가 올린 것과 오늘 정해야 할 것."
          provenance={{
            kind: "unavailable",
            reason: "리서치 저녁 배치가 아직 없어 어젯밤에 올라온 것이 없습니다",
          }}
        />
      </div>
    </div>
  );
}
