import { PRODUCT_STAGES, ROADMAP_URL, STAGE_LABELS, type StageState } from "@/constants/stages";
import { cn } from "@/components/shared/ui/primitives/cn";

const ORDER: readonly StageState[] = ["now", "next", "later", "not-now"];

/** 지금 되는 것만 진하게 — 나머지는 「있다」는 것만 보이면 된다. */
const TONE: Record<StageState, string> = {
  now: "text-ink",
  next: "text-ink-muted",
  later: "text-ink-muted",
  "not-now": "text-ink-muted line-through",
};

/**
 * 제품 전체의 남은 단계 — 「굴린다더니 안 되네」가 이슈로 돌아오기 전에 화면이 먼저 말한다.
 *
 * 접어 둔다: 첫 화면에서 할 일(봇 만들기·적재)보다 앞에 서면 안 되고, 그렇다고 문서로만
 * 두면 찾는 사람만 본다.
 */
export function ProductStages() {
  return (
    <details className="min-w-0 border border-line px-3 py-2">
      <summary className="cursor-pointer break-keep text-sm text-ink marker:text-ink-muted">
        이 제품이 지금 어디까지 왔나
      </summary>

      <dl className="mt-2 flex flex-col gap-1.5">
        {ORDER.map((state) => {
          const stages = PRODUCT_STAGES.filter((stage) => stage.state === state);
          if (stages.length === 0) return null;

          return (
            <div key={state} className="flex min-w-0 flex-wrap items-baseline gap-x-2">
              <dt className="w-24 flex-none text-2xs text-ink-muted">{STAGE_LABELS[state]}</dt>
              <dd className="min-w-0 flex-1">
                <ul className="flex flex-col gap-0.5">
                  {stages.map((stage) => (
                    <li key={stage.id} className="min-w-0 break-keep text-2xs">
                      <span className={cn(TONE[state])}>{stage.label}</span>
                      {stage.note && <span className="text-ink-muted"> — {stage.note}</span>}
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          );
        })}
      </dl>

      <p className="mt-2 text-2xs text-ink-muted">
        순서와 상세는{" "}
        <a href={ROADMAP_URL} target="_blank" rel="noreferrer" className="underline underline-offset-2">
          ROADMAP.md
        </a>{" "}
        가 정본입니다.
      </p>
    </details>
  );
}
