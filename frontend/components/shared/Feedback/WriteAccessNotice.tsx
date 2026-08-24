import {
  WRITE_DENIED_CAN_DO,
  WRITE_DENIED_HOW,
  WRITE_DENIED_REASON,
  WRITE_DENIED_TITLE,
} from "@/constants/writeAccess";

/**
 * 「이 계정은 저장·실행이 막혀 있다」를 화면 머리에서 **누르기 전에** 말하는 자리 (#341).
 *
 * 순서는 `features/Bench/ImpactNotice` 와 같은 문법이다 — 머리줄 → 멈추는 것 / 계속 도는 것
 * → 원인·해법. 그 컴포넌트를 직접 쓰지 않는 이유는 층 방향이다: 이 배너는 `/admin` 의
 * 관심종목·포트폴리오·스케줄러에도 서므로 `shared` 에 살아야 하고, `shared` 가 `features` 를
 * import 하면 층이 거꾸로 뒤집힌다.
 *
 * **판정은 여기서 하지 않는다** — `useWriteAccess` 가 하고 이 컴포넌트는 그리기만 한다.
 * `Feedback/index.ts` 는 RootLayout 이 끌어가는 배럴이라 여기에 세션 클라이언트를 물리면
 * 전 라우트가 그것을 지고 간다(그 배럴 주석의 불변식). 같은 이유로 배럴에서 재수출하지
 * 않는다 — 소비자가 이 파일을 직접 import 한다(`Loading` 과 같은 관례).
 *
 * 색은 디자인 시스템 토큰만 쓴다 — 이 띠는 다크(실험대·시세)와 라이트(`/admin`) 양쪽에 선다.
 * 머리줄이 `--caution` 인 이유: 고장이 아니라 **권한이 그렇게 정해져 있는 상태**라 오류(`--danger`)
 * 로 내면 진짜 오류가 묻힌다 (디자인 시스템 §2.2).
 */
export function WriteAccessNotice({
  /** 이 화면에서 막히는 동작. 화면마다 다르므로 부르는 쪽이 준다 */
  halted,
  className = "",
}: {
  halted: string[];
  className?: string;
}) {
  return (
    <div role="status" className={`w-full min-w-0 rounded-panel border border-line bg-bg-raised p-3 ${className}`}>
      <p className="break-keep font-ui text-sm text-caution">{WRITE_DENIED_TITLE}</p>

      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-2xs text-ink-muted">막히는 것</dt>
          <dd className="mt-0.5 break-keep text-sm text-ink">{halted.length > 0 ? halted.join(" · ") : "없음"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-2xs text-ink-muted">계속 되는 것</dt>
          <dd className="mt-0.5 break-keep text-sm text-ink">{WRITE_DENIED_CAN_DO}</dd>
        </div>
      </dl>

      <p className="mt-2 break-keep text-2xs text-ink-muted">{WRITE_DENIED_REASON}</p>
      <p className="mt-1 break-keep text-2xs text-ink-muted">{WRITE_DENIED_HOW}</p>
    </div>
  );
}
