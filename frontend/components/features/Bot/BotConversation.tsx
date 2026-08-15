"use client";

/**
 * 대화 자리 — 실험대 스펙 §8.6.1 「문이 두 개다」의 왼쪽 문.
 *
 * 아직 붙지 않았다. **자리를 비워두되 왜 비었는지 적는다** — 빈 칸만 있으면 "고장"으로 읽히고,
 * 그럴싸한 가짜 대화를 채우면 "된다"로 읽힌다. 지금 할 수 있는 것(오른쪽 폼)을 함께 가리킨다.
 */
export function BotConversation() {
  return (
    <section className="flex min-h-[12rem] flex-col border border-slate-line bg-slate-panel">
      <header className="border-b border-slate-line px-3 py-2">
        <h2 className="font-mono text-xs text-ink-primary">대화</h2>
      </header>
      <div className="flex flex-1 flex-col justify-center gap-2 px-4 py-6 text-sm">
        <p className="text-ink-primary">말로 조건을 정하는 문은 아직 열리지 않았습니다.</p>
        <p className="leading-relaxed text-ink-muted">
          여기서 &ldquo;코스피 대형주 눌림목 봇&rdquo; 처럼 말하면 오른쪽 폼이 채워지게 됩니다. 그동안은 오른쪽에서 직접
          정할 수 있고, 정한 것은 대화가 붙은 뒤에도 그대로 남습니다.
        </p>
      </div>
    </section>
  );
}
