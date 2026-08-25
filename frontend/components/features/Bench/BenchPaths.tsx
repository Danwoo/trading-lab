"use client";

import Link from "next/link";

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
    /**
     * 같은 화면을 여는 **주소 있는 문**. 홈이 처음 온 사람에게 내미는 길이라 여기만은 주소로
     * 보낸다 — 열 칸 넘는 폼을 채우다 새로고침하면 패널은 통째로 사라지고 돌아올 자리도 없다
     * (#347). 레일의 「봇」은 §20.2 대로 패널을 계속 연다.
     */
    href: "/bench/bot/new",
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
 * 두 갈래는 **자리가 실재하는 쪽으로 보낸다.** 화면이 이미 라우트로 있으면 그 주소로 가고
 * (`href`), 아직 패널뿐이면 레일의 해당 패널을 연다. 목적지 화면을 여기서 만들지 않는다 —
 * 대신 그 자리가 아직 준비 중이면 레일 항목이 스스로 적어 둔 `pending` 한 줄을 카드 밑에
 * 그대로 보인다. 준비가 끝나 `pending` 이 사라지면 이 줄도 함께
 * 사라진다. **눌렀는데 아무 일도 안 일어나는 것**이 이 화면에서 제일 나쁜 결과라 그것만은 막는다.
 *
 * 그 한 줄은 **중립 잉크**로 적는다. 준비 중은 계획대로인 상태라 고장 난 것이 없고 사용자가 할
 * 일도 없다 — 상태색을 쓰면 처음 온 사람이 제품을 고장으로 읽는다(디자인 시스템 §2.2).
 *
 * 폭을 고정하지 않는다 — 자리가 있으면 나란히, 좁아지면 쌓인다.
 */
const CARD_CLASS =
  "min-w-0 flex-1 rounded-control border border-line bg-bg-raised px-3 py-2 text-left transition-colors hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted";

export function BenchPaths() {
  const openPanel = useProductPanelStore((s) => s.open);

  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row">
      {PATHS.map((path) => {
        const rail = RAIL_ITEMS.find((item) => item.id === path.railId);
        const body = (
          <>
            <span className="block break-keep text-sm font-ui text-ink">{path.title}</span>
            <span className="mt-0.5 block break-keep text-2xs text-ink-muted">{path.hint}</span>
            {rail?.pending && (
              <span className="mt-1 block break-keep text-2xs text-ink-muted">준비 중 — {rail.pending}</span>
            )}
          </>
        );
        return "href" in path ? (
          <Link key={path.railId} href={path.href} className={CARD_CLASS}>
            {body}
          </Link>
        ) : (
          <button key={path.railId} type="button" onClick={() => openPanel(path.railId)} className={CARD_CLASS}>
            {body}
          </button>
        );
      })}
    </div>
  );
}
