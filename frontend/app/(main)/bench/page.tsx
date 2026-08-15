/**
 * 실험대 — 제품의 홈 (화면 결정 §20.2 「㉮ 실험대가 홈」).
 *
 * **S2 는 자리만 만든다.** 보드에 상시로 있는 것은 넷(격자·곡선·내 봇·오늘 할 일)이고,
 * 격자·곡선은 백테스트·봇 엔진 산출물이라 마일스톤 2 의 no-go 다 — 빈 상태(§21.4)까지가
 * S4 의 몫이라 여기서는 **무엇이 올 자리인지**만 적는다. 실루엣만 남기지 않는다는 §21.4 의
 * 규칙을 이 골조 단계에서도 지킨다.
 */
const BOARD_ZONES = [
  { title: "격자", note: "파라미터 조합 100가지. 칸을 누르면 곡선이 바뀝니다." },
  { title: "곡선", note: "자산 추이 + 구간 브러시. 구간을 끌면 그 구간만 다시 계산합니다." },
  { title: "내 봇", note: "만든 봇 목록과 지금 상태." },
  { title: "오늘 할 일", note: "어젯밤에 한 일 · 정해야 할 것." },
];

export default function Page() {
  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header>
        <h1 className="text-lg font-medium text-ink-primary">실험대</h1>
        <p className="mt-1 text-sm text-ink-muted">
          봇을 만들고 검증하고 굴리는 자리입니다. 아래 넷이 이 화면에 상시로 놓입니다.
        </p>
      </header>

      <ul className="grid min-h-0 flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
        {BOARD_ZONES.map((zone) => (
          <li key={zone.title} className="rounded border border-dashed border-slate-line bg-slate-panel p-4">
            <h2 className="text-sm font-medium text-ink-primary">{zone.title}</h2>
            <p className="mt-1 text-sm text-ink-muted">{zone.note}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
