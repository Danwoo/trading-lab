/**
 * `unavailable` 일 때 패널 본문 대신 렌더된다 — 빈 껍데기가 아니라 이유를 설명한다 (FR-021).
 */
export function PanelUnavailable({ reason }: { reason: string }) {
  return (
    <div role="status" className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <svg viewBox="0 0 24 24" width="24" height="24" className="text-ink-muted" aria-hidden="true">
        <circle cx="12" cy="12" r="9.3" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6.5 12h11" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      <p className="text-sm text-ink-muted">{reason}</p>
    </div>
  );
}
