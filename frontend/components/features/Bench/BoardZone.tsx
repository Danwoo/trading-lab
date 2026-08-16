import type * as React from "react";
import { ProvenanceBadge } from "@/components/features/Terminal/ProvenanceBadge";
import { cn } from "@/components/shared/ui/primitives/cn";
import type { Provenance } from "@/types/terminal/provenance";

interface Props {
  title: string;
  /**
   * **여기에 무엇이 올 것인가** — §21.4 「실루엣만 남기지 않는다」의 본체다.
   * 비어 있는 자리에 이 한 줄이 없으면 고장 난 화면과 구분되지 않는다.
   */
  incoming: string;
  /** 이 자리의 출처. `unavailable` 의 `reason` 이 「지금 왜 비어 있나」다 */
  provenance: Provenance;
  /** 보드↔패널 선택이 이 자리를 가리키고 있나 (§20.2) */
  marked?: boolean;
  /**
   * 이 자리가 **실패**했을 때의 알림(`ImpactNotice`). 주면 `reason` 한 줄을 **대신한다** —
   * 둘 다 내면 원인 문구가 영향 범위 위에 서서 §21.5 의 순서가 뒤집힌다. 원인은 알림의
   * `detail` 로 내려가 맨 뒤에 온다.
   */
  notice?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * 보드에 상시로 있는 넷(§20.2) 중 한 자리.
 *
 * 빈 자리도 **출처를 갖는다** — 헤더의 배지는 터미널 패널이 쓰는 것과 같은 장치이고,
 * `unavailable` 의 `reason` 이 타입으로 강제되므로 이유 없는 빈 화면이 컴파일되지 않는다.
 *
 * 폭·높이를 px 로 박지 않는다. 부모 격자가 주는 자리를 채우고, 글은 잘리지 않고 접힌다.
 */
export function BoardZone({ title, incoming, provenance, marked = false, notice, children }: Props) {
  const reason = provenance.kind === "unavailable" ? provenance.reason : null;

  return (
    <section
      aria-label={title}
      className={cn(
        "flex min-w-0 flex-col rounded-panel border border-line bg-bg-panel p-3",
        marked && "border-line-strong",
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <h2 className="min-w-0 break-keep text-sm font-ui text-ink">{title}</h2>
        <span className="text-2xs">
          <ProvenanceBadge provenance={provenance} />
        </span>
      </div>

      <p className="mt-1 break-keep text-2xs text-ink-muted">{incoming}</p>

      {notice ? (
        <div className="mt-2 min-w-0">{notice}</div>
      ) : (
        reason && (
          <p role="status" className="mt-2 break-keep text-sm text-ink">
            {reason}
          </p>
        )
      )}

      {children && <div className="mt-2 min-w-0">{children}</div>}
    </section>
  );
}
