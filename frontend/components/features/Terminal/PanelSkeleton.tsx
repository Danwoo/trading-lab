/**
 * 지연 로드(`PanelDefinition.load`) 중 보여주는 콘텐츠 자리 스켈레톤 — 스피너가 아니다.
 * 패널은 크기가 고정돼 있어 스피너로 바꿔치면 배치가 흔들린다 (설계 §3.5).
 */
export function PanelSkeleton() {
  return (
    <div className="flex h-full flex-col gap-2 p-3" aria-busy="true" aria-label="패널을 불러오는 중">
      <div className="h-3 w-2/5 rounded-sm bg-slate-line motion-safe:animate-pulse" />
      <div className="h-full w-full rounded-sm bg-slate-line motion-safe:animate-pulse" />
    </div>
  );
}
