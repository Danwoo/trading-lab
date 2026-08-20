import type * as React from "react";
import { cn } from "@/components/shared/ui/primitives/cn";

/**
 * 머리줄이 갖는 세 칸. **오류와 정상 사이에 한 칸이 있어야** 그 사이 상태가 오류 쪽으로
 * 뭉개지지 않는다 (디자인 시스템 §2.2).
 *
 * - `alert` — 지금 잘못됐다. 실패했거나 못 읽었다
 * - `caution` — 잘못되진 않았는데 그대로 두면 안 된다. 사용자가 손댈 것이 이미 있다
 * - `quiet` — 계획대로다. 「아직 안 온 것」·「받는 중」이 여기 온다
 */
export type ImpactTone = "alert" | "caution" | "quiet";

/** 색은 토큰만 쓴다 — 이 표가 상태 → 색의 유일한 대응이다. */
const TONE_CLASS: Record<ImpactTone, string> = {
  alert: "text-danger",
  caution: "text-caution",
  quiet: "text-ink",
};

interface Props {
  /** 무슨 일이 일어났나. 한 줄로 */
  headline: string;
  /** 이 일 때문에 **멈추는 것**. 빈 배열이면 「없음」으로 적는다 — 안 적으면 안 멈춘 건지 모르는 건지 갈리지 않는다 */
  halted: string[];
  /** 그래도 **계속 도는 것** */
  running: string[];
  /** 원인 문구(서버 사유·예외 메시지). **맨 뒤에 온다** */
  detail?: string | null;
  /** 사용자가 지금 할 수 있는 것 (링크·버튼) */
  action?: React.ReactNode;
  /** 머리줄을 어느 칸으로 낼 것인가 (`ImpactTone`). 「받는 중」처럼 나쁜 소식이 아닌 상태는 조용히 낸다 */
  tone?: ImpactTone;
}

function Scope({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-ink-muted">{label}</dt>
      <dd className="mt-0.5 break-keep text-sm text-ink">{items.length > 0 ? items.join(" · ") : "없음"}</dd>
    </div>
  );
}

/**
 * 실패를 **영향 범위부터** 말한다 — 화면 결정 §21.5.
 *
 * 순서가 이 컴포넌트의 전부다. 사람이 실패 앞에서 실제로 묻는 것은 「무슨 오류인가」가 아니라
 * **「지금 보는 숫자를 믿어도 되나」**이고, 그 답은 「무엇이 멈추고 무엇이 계속 도는가」다.
 * 원인 문구를 위에 두면 그 답이 스크롤 아래로 밀리므로 `detail` 은 항상 맨 뒤에 온다.
 *
 * 폭을 고정하지 않는다 — 부모를 채우고, 두 갈래는 자리가 나면 나란히 서고 좁아지면 쌓인다.
 */
export function ImpactNotice({ headline, halted, running, detail, action, tone = "alert" }: Props) {
  return (
    <div className="w-full min-w-0 rounded-panel border border-line bg-bg-raised p-3">
      <p className={cn("break-keep text-sm font-ui", TONE_CLASS[tone])}>{headline}</p>

      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
        <Scope label="멈추는 것" items={halted} />
        <Scope label="계속 도는 것" items={running} />
      </dl>

      {detail && <p className="mt-2 break-words text-2xs text-ink-muted">{detail}</p>}
      {action && <div className="mt-2 flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}
