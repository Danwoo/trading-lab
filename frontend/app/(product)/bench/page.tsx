/**
 * 실험대 — 홈 (화면 설계 §20.2 「㉮ 실험대가 홈」).
 *
 * S2 는 **자리**까지다. 보드에 상시로 있는 넷(격자·곡선·내 봇·오늘 할 일)은 백테스트·봇 엔진
 * 산출물이라 S4(빈 상태)가 채운다 — 여기서는 그 자리가 무엇의 자리인지만 적는다.
 */
export default function Page() {
  return (
    <div className="flex h-full flex-col gap-3 p-6">
      <h1 className="text-lg font-medium text-ink-primary">실험대</h1>
      <p className="max-w-prose text-sm text-ink-muted">
        봇을 만들고, 돌려보고, 의심하는 자리입니다. 왼쪽 레일에서 봇·거래 로그·내 기준을 열면 이 화면을 덮지 않고 옆에
        붙습니다.
      </p>
      <ul className="max-w-prose list-disc space-y-1 pl-5 text-sm text-ink-muted">
        <li>격자 — 설정 조합마다의 성적</li>
        <li>곡선 — 고른 조합이 그린 자산 곡선</li>
        <li>내 봇 — 지금 돌고 있는 것</li>
        <li>오늘 할 일 — 봇이 모르는 것(실적·공시)이 올라오는 자리</li>
      </ul>
    </div>
  );
}
