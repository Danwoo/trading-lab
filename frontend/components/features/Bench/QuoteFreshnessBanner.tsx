"use client";

import Link from "next/link";
import { ProvenanceBadge } from "@/components/features/Terminal/ProvenanceBadge";
import { ImpactNotice } from "@/components/features/Bench/ImpactNotice";
import { MARKET_PATH } from "@/constants/routes";
import { useQuoteFreshness } from "@/hooks/bench/useQuoteFreshness";

/** 적재를 실제로 돌릴 수 있는 자리로 보낸다 — 안내만 하고 갈 곳을 안 주면 그것도 막다른 길이다. */
function GoLoadLink() {
  return (
    <Link
      href={MARKET_PATH}
      className="inline-flex min-h-touch-min items-center rounded-control border border-line px-2 py-1 text-2xs text-ink hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
    >
      시세로 가서 적재하기
    </Link>
  );
}

/**
 * 보드 상단의 **상시** 시세 신선도 표시 — 화면 결정 §21.5.
 *
 * 이 띠가 이 화면에서 가장 중요한 한 줄이다. §21.5 의 「절대 안 하는 것 — 조용히 낡은 값으로
 * 계속 굴리는 것」이 지켜지는지가 여기서 눈에 보인다. 그래서 **낡았을 때만 뜨는 경고가 아니라
 * 늘 떠 있는 상태 표시**다 — 아무 배지도 없는 화면은 「최신이다」와 「아무도 안 봤다」를 구분해
 * 주지 않는다.
 *
 * 출처 배지는 터미널 패널이 쓰는 것과 같은 장치를 그대로 쓴다(`ProvenanceBadge`). 낡음 판정만
 * `staleness` 로 얹었다 — 「시세 · 08-06 · 하루 낡음」이 §21.5 가 적은 배지 문구다.
 */
export function QuoteFreshnessBanner() {
  const freshness = useQuoteFreshness();

  const badge = (
    <span className="text-2xs">
      <ProvenanceBadge provenance={freshness.provenance} staleness={freshness.staleness} precision="day" />
    </span>
  );

  if (freshness.kind === "checking" || freshness.kind === "fresh") {
    return (
      <section aria-label="시세 신선도" className="flex w-full flex-wrap items-center gap-x-3 gap-y-1">
        {badge}
        {freshness.kind === "fresh" && (
          <span className="break-keep text-2xs text-ink-muted">오늘 적재본입니다 — 신호 판정이 정상입니다.</span>
        )}
        {freshness.running && <span className="break-keep text-2xs text-ink-muted">적재가 지금 돌고 있습니다.</span>}
      </section>
    );
  }

  return (
    <section aria-label="시세 신선도" className="flex w-full flex-col gap-2">
      {badge}
      {freshness.kind === "stale" && (
        <ImpactNotice
          headline={`시세 적재본이 ${freshness.staleness?.label ?? "낡음"} 상태입니다 — 오늘 값으로 판정하지 않습니다`}
          halted={["오늘 신호 판정"]}
          running={["격자·과거 성적 (적재된 구간까지)"]}
          detail={freshness.failedReason}
          action={<GoLoadLink />}
        />
      )}
      {freshness.kind === "never-run" && (
        <ImpactNotice
          tone={freshness.running ? "quiet" : "alert"}
          headline={
            freshness.running
              ? "첫 캔들 적재가 돌고 있습니다 — 끝나면 이 줄이 날짜로 바뀝니다"
              : "캔들 적재를 아직 한 번도 돌리지 않았습니다"
          }
          halted={["오늘 신호 판정", "차트"]}
          running={["봇 만들기", "조건 편집"]}
          action={<GoLoadLink />}
        />
      )}
      {freshness.kind === "never-succeeded" && (
        <ImpactNotice
          headline="캔들 적재가 아직 한 번도 성공하지 못했습니다"
          halted={["오늘 신호 판정", "차트"]}
          running={["봇 만들기", "조건 편집"]}
          detail={freshness.failedReason}
          action={<GoLoadLink />}
        />
      )}
      {freshness.kind === "unreadable" && (
        <ImpactNotice
          headline="시세가 얼마나 낡았는지 확인하지 못했습니다 — 모르는 것을 최신으로 두지 않습니다"
          halted={["오늘 신호 판정", "신선도 판정"]}
          running={["봇 만들기", "조건 편집"]}
          detail={freshness.failedReason}
          action={<GoLoadLink />}
        />
      )}
    </section>
  );
}
