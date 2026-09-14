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
import {
  GRID_RUN_FAILED_HEADLINE,
  curveZoneProvenance,
  gridZoneProvenance,
  rosterZoneProvenance,
  type RosterState,
} from "@/lib/bench/boardProvenance";
import { reportTimingLine } from "@/lib/bench/reportTiming";
import { BOT_ROLE_LABEL } from "@/schemas/bot/bot";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { ProductStages } from "@/components/features/Bench/ProductStages";
import { WriteAccessNotice } from "@/components/shared/Feedback/WriteAccessNotice";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";

/** 좁은 화면에서 하나씩 보여주는 둘 (§21.6 「보드가 먼저 양보한다」) */
const TABBED_ZONE_IDS = ["grid", "curve"] as const;
type TabbedZoneId = (typeof TABBED_ZONE_IDS)[number];

const TAB_TITLES: Record<TabbedZoneId, string> = { grid: "격자", curve: "곡선" };

/** 「시작하는 길」의 머리말. `filled` 는 개수를 넣어야 해서 부르는 쪽이 만든다. */
const PATHS_LEAD: Record<Exclude<RosterState, "filled">, string> = {
  loading: "봇 목록을 확인하고 있습니다. 그동안 두 갈래 중 하나로 시작하셔도 됩니다.",
  unreadable: "봇 목록을 읽지 못해 몇 개인지 모릅니다. 두 갈래는 그대로 쓰실 수 있습니다.",
  empty: "아직 봇이 없습니다. 두 갈래 중 하나로 시작하시면 됩니다.",
};

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
  const writeAccess = useWriteAccess();

  const bots = roster.data;
  const botCount = bots?.length ?? 0;
  const rosterUnreadable = roster.provenance.kind === "unavailable";
  //  「봇이 0개다」는 목록을 **읽고 나서야** 할 수 있는 말이다. 아직 안 왔거나 못 읽었는데
  //  0으로 세면, 봇이 있는 사용자에게 없다고 말하게 된다 (실측: 느린 응답에서 1.5초 동안,
  //  백엔드가 죽으면 계속). 네 상태를 한 곳에서 정해 자리마다 다시 판단하지 않게 한다.
  const rosterState: RosterState =
    roster.isLoading && bots === null
      ? "loading"
      : rosterUnreadable
        ? "unreadable"
        : botCount === 0
          ? "empty"
          : "filled";

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

  // 격자·곡선이 비어 있는 이유는 상태마다 다르다. 「봇이 없다」·「아직 안 돌렸다」·「돌렸는데
  // 실패했다」·「칸을 아직 안 골랐다」를 한 문장으로 뭉개면 무엇을 하면 되는지가 사라진다.
  const gridProvenance = gridZoneProvenance({
    rosterState,
    hasGrid: board.grid !== null,
    isRunning: board.isRunning,
    runError: board.runError,
  });

  const curveProvenance = curveZoneProvenance({
    rosterState,
    hasGrid: board.grid !== null,
    isRunning: board.isRunning,
    runError: board.runError,
    report: activeReport && { runId: activeReport.run.run_id, finishedDt: activeReport.run.finished_dt },
    isReportLoading: board.isReportLoading,
    reportError: board.reportError,
  });

  const rosterProvenance = rosterZoneProvenance(rosterState, roster.provenance);

  const gridZone = (
    <BoardZone
      title="격자"
      incoming="파라미터 조합이 칸으로 깔립니다. 칸을 누르면 곡선이 그 조합으로 바뀝니다."
      provenance={gridProvenance}
      marked={selection?.kind === "grid-point"}
      notice={
        board.runError !== null ? (
          <ImpactNotice
            headline={GRID_RUN_FAILED_HEADLINE}
            halted={board.grid !== null ? ["새 격자"] : ["격자", "곡선·지표·거래"]}
            running={board.grid !== null ? ["앞선 격자의 칸 고르기"] : ["봇 만들기", "시세 보기"]}
            detail={board.runError}
            announce
          />
        ) : undefined
      }
    >
      <SelectionLine selection={selection} kind="grid-point" />
      {rosterState === "filled" && (
        <div className="flex min-w-0 flex-col gap-3">
          <GridRunForm bots={bots} controller={runForm} isRunning={board.isRunning} onRun={board.runGrid} />
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
            <p className="break-keep text-2xs text-ink-muted">{reportTimingLine(board.lastReportMs)}</p>
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
          봇을 만들고, 과거 데이터로 검증하는 자리입니다. 아래 넷이 이 화면에 상시로 놓입니다.
          <br />
          굴리기(장중 실행·주문)는 아직 없습니다 — 무엇이 언제 오는지는 아래에 적어 두었습니다.
        </p>
      </header>

      <ProductStages />

      {/* 이 계정이 저장·실행을 못 한다면 보드에 손대기 전에 먼저 말한다 (#341). */}
      {writeAccess.isDenied && <WriteAccessNotice halted={["봇 저장·삭제", "격자 실행"]} />}

      <QuoteFreshnessBanner />

      <section aria-label="시작하는 길" className="min-w-0">
        <p className="mb-2 break-keep text-sm text-ink">
          {rosterState === "filled"
            ? `봇 ${botCount}개가 있습니다. 하나 더 만드시려면 여기서 시작하시면 됩니다.`
            : PATHS_LEAD[rosterState]}
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
                    {BOT_ROLE_LABEL[bot.bot_role]} · {bot.use_at === "Y" ? "켜짐" : "꺼짐"}
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
            because: "no-source",
          }}
        />
      </div>
    </div>
  );
}
