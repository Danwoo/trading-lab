import type * as React from "react";
import type { Provenance } from "@/types/terminal/provenance";
import { formatDate } from "@/utils/common/formatters/date";

interface IconProps {
  className?: string;
}

/** 살아있음(●) — live. 정적 아이콘, 신선도는 asOf 텍스트가 갱신되는 것으로 보여준다(애니메이션 없음). */
function LiveIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 8 8" width="8" height="8" className={className} aria-hidden="true">
      <circle cx="4" cy="4" r="4" fill="currentColor" />
    </svg>
  );
}

/** 적재본 — loaded. */
function LoadedIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        d="M2 4c0-1.1 2.7-2 6-2s6 .9 6 2-2.7 2-6 2-6-.9-6-2Zm0 0v8c0 1.1 2.7 2 6 2s6-.9 6-2V4M2 8c0 1.1 2.7 2 6 2s6-.9 6-2"
      />
    </svg>
  );
}

/** 임시 데이터 — placeholder. 측량 테이프 해칭과 같은 어휘의 작은 아이콘. */
function PlaceholderIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} aria-hidden="true">
      <g stroke="currentColor" strokeWidth="1.3">
        <path d="M2 14 14 2" />
        <path d="M2 9 9 2" strokeWidth="1" opacity="0.7" />
        <path d="M7 14 14 7" strokeWidth="1" opacity="0.7" />
      </g>
    </svg>
  );
}

/** 제공 안 됨 — unavailable. */
function UnavailableIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} aria-hidden="true">
      <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4.5 8h7" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

/** 출처 미상 — provenance 가 null. 조용히 통과시키지 않는 경고. */
function UnknownProvenanceIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} aria-hidden="true">
      <path fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" d="M8 1.5 15 14.5H1L8 1.5Z" />
      <path d="M8 6.2v3.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="8" cy="11.8" r="0.9" fill="currentColor" />
    </svg>
  );
}

function formatHeaderTimestamp(asOf: string): string | null {
  const full = formatDate(asOf, "datetime");
  if (!full) return null;
  const [datePart, timePart] = full.split(" ");
  return `${datePart.slice(5)} ${timePart.slice(0, 5)}`;
}

/**
 * 출처 표시 — 색만으로 구분하지 않는다. 아이콘 + 텍스트를 항상 함께 낸다.
 * `provenance` 가 `null` 이면 패널이 아직 아무 출처도 보고하지 않은 것 — 조용히 통과시키지 않고
 * "출처 미상" 경고로 렌더한다.
 */
export function ProvenanceBadge({ provenance }: { provenance: Provenance | null }): React.ReactElement {
  if (provenance === null) {
    return (
      <span className="inline-flex items-center gap-1 text-signal-warn" role="status">
        <UnknownProvenanceIcon />
        출처 미상
      </span>
    );
  }

  switch (provenance.kind) {
    case "live": {
      const timestamp = provenance.asOf ? formatHeaderTimestamp(provenance.asOf) : null;
      return (
        <span className="inline-flex items-center gap-1 text-ink-primary">
          <LiveIcon />
          {provenance.source} · 실시간{timestamp ? ` · ${timestamp}` : ""}
        </span>
      );
    }
    case "loaded": {
      const timestamp = provenance.asOf ? formatHeaderTimestamp(provenance.asOf) : null;
      return (
        <span className="inline-flex items-center gap-1 text-ink-muted">
          <LoadedIcon />
          {provenance.source}
          {timestamp ? ` · ${timestamp}` : ""}
        </span>
      );
    }
    case "placeholder":
      return (
        <span className="inline-flex items-center gap-1 text-signal-warn" role="status">
          <PlaceholderIcon />
          {provenance.source}
          {provenance.note ? ` · ${provenance.note}` : ""}
        </span>
      );
    case "unavailable":
      return (
        <span className="inline-flex items-center gap-1 text-ink-muted">
          <UnavailableIcon />
          제공 안 됨
        </span>
      );
  }
}
