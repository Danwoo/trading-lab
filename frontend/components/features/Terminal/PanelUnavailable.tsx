import Link from "next/link";

/**
 * `unavailable` 일 때 패널 본문 대신 렌더된다 — 빈 껍데기가 아니라 이유를 설명한다 (FR-021).
 */
export function PanelUnavailable({
  reason,
  action,
}: {
  reason: string;
  /** 사유를 읽고 **바로 갈 수 있는 자리**. 「어디로 가라」만 적고 링크를 안 주면 막다른 길이 된다. */
  action?: { href: string; label: string };
}) {
  return (
    <div role="status" className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <svg viewBox="0 0 24 24" width="24" height="24" className="text-ink-muted" aria-hidden="true">
        <circle cx="12" cy="12" r="9.3" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6.5 12h11" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      <p className="text-sm text-ink-muted">{reason}</p>
      {action && (
        <Link
          href={action.href}
          className="rounded-control border border-line px-2.5 py-1 text-2xs text-ink hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
