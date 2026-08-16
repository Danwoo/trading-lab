"use client";

import { RAIL_ITEMS } from "@/constants/shell";
import { useProductPanelStore } from "@/stores/shell/productPanelStore";

/**
 * §21.4 가 못박은 **길 둘**. 실험대의 두 갈래이고, 순서도 그 문장의 순서다.
 *
 * `railId` 는 이 길이 실제로 여는 자리다 — 문구만 있고 가는 곳이 없으면 그것이 죽은 링크다.
 */
const PATHS = [
  {
    railId: "bot",
    title: "봇 만들기",
    hint: "어떤 조건일 때 사고 파는지 직접 정합니다.",
  },
  {
    railId: "agent",
    title: "에이전트에게 맡기기",
    hint: "무엇을 하고 싶은지 말하면 조건을 대신 짜 옵니다.",
  },
] as const;

/**
 * 빈 보드가 주는 두 갈래 — 화면 결정 §21.4 「길을 둘 준다」.
 *
 * 두 버튼은 **레일의 해당 패널을 실제로 연다.** 목적지 화면을 여기서 만들지 않는다(그것은
 * `#150` 봇 만들기의 몫이다) — 대신 그 자리가 아직 준비 중이면 레일 항목이 스스로 적어 둔
 * `pending` 한 줄을 버튼 밑에 그대로 보인다. 준비가 끝나 `pending` 이 사라지면 이 줄도 함께
 * 사라진다. **눌렀는데 아무 일도 안 일어나는 것**이 이 화면에서 제일 나쁜 결과라 그것만은 막는다.
 *
 * 폭을 고정하지 않는다 — 자리가 있으면 나란히, 좁아지면 쌓인다.
 */
export function BenchPaths() {
  const openPanel = useProductPanelStore((s) => s.open);

  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row">
      {PATHS.map((path) => {
        const rail = RAIL_ITEMS.find((item) => item.id === path.railId);
        return (
          <button
            key={path.railId}
            type="button"
            onClick={() => openPanel(path.railId)}
            className="min-w-0 flex-1 rounded-control border border-line bg-bg-raised px-3 py-2 text-left transition-colors hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <span className="block break-keep text-sm font-ui text-ink">{path.title}</span>
            <span className="mt-0.5 block break-keep text-2xs text-ink-muted">{path.hint}</span>
            {rail?.pending && (
              <span className="mt-1 block break-keep text-2xs text-danger">준비 중 — {rail.pending}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
