import { ADMIN_PATH, BENCH_PATH, MARKET_PATH } from "@/constants/routes";

/**
 * §21.6 의 폭 구간 경계.
 *
 * - 1280 이상: 보드는 격자+곡선 나란히, 패널 372(에이전트는 620까지)
 * - 1024~1280: 보드는 격자/곡선 탭으로 하나씩, 패널 300
 * - 1024 미만: 보드는 탭, 패널이 **보드를 덮는다**
 *
 * **구간을 고르는 것은 CSS 다** — 위 세 줄은 Tailwind 기본 `xl`(1280)·`lg`(1024) 로 표현되고
 * 폭 값은 `styles/globals.css` 의 `--shell-*` 가 갖는다. 여기 두 숫자는 그 경계를 이름으로
 * 남기고, JS 가 하나 남은 판단(패널이 보드를 덮는가 — `inert`)에 쓰라고 있는 것이다.
 * 이 값이 Tailwind 의 `lg`·`xl` 과 어긋나면 `tests/styles/shellTokens.test.ts` 가 실패한다.
 *
 * 모바일은 다루지 않는다 — 격자를 손가락으로 고르는 것도 손으로 적는 칸도 성립하지 않아
 * 별도 설계가 필요하고 지금 범위 밖이다(§21.6).
 */
export const VIEWPORT_WIDE_MIN_PX = 1280;
export const VIEWPORT_COMPACT_MIN_PX = 1024;

/**
 * 레일 항목 하나.
 *
 * `kind` 가 §20.2 「이동 규칙」의 두 갈래를 그대로 나눈다 — `route` 는 화면을 바꾸고,
 * `panel` 은 보드를 그대로 둔 채 옆 패널만 열고 닫는다.
 */
export interface RailItem {
  id: string;
  label: string;
  /** `components/shared/ui/primitives/icons.tsx` 의 키 */
  icon: string;
  kind: "route" | "panel";
  /** `kind: "route"` 이고 화면이 실재할 때의 경로. 없으면 아직 안 만든 자리다 */
  path?: string;
  /**
   * 아직 못 여는 자리의 이유. **비워 두지 않는다** — 아무 반응 없는 버튼은 고장으로 읽힌다
   * (§21.4 「실루엣만 남기지 않는다」). 화면이 붙으면 이 줄이 사라진다.
   */
  pending?: string;
  /** 372 ↔ 620 토글을 주는 패널. §21.3 이 **에이전트에만** 준 예외다 */
  expandable?: boolean;
  /** 이 항목 다음에 구분선을 긋는다 */
  dividerAfter?: boolean;
  /** 레일 바닥에 붙인다 (위 묶음과 떨어뜨린다) */
  footer?: boolean;
}

/**
 * 레일 순서 — 화면 결정 §20.2 의 확정값이자 `bench-shell.html` 시안의 배치다.
 *
 * 실험대 · 리서치 / 봇 · 에이전트 · 거래 로그 · 내 기준 / 시세 · 포트폴리오 / (바닥) 설정.
 * §20.2 본문은 리서치를 셋째 묶음에 적었는데, 같은 문서 §22.5 가 리서치를 **동등한 기둥**으로
 * 올리며 전체 폭 화면을 주기로 했다 — 시안(`bench-shell.html`)과 `#73` 계획의 열거가 둘 다
 * 실험대 옆이라 그쪽을 따랐다.
 *
 * 「에이전트」는 §20.2 의 열거에 없다. §20.4 가 그 자리를 미결로 남겼고 **§21.3 이 「패널
 * 372 ↔ 620 토글」로 닫았다** — 패널이라면 그것을 여는 자리는 레일이다. 봇 옆에 둔 것은
 * §21.4 가 첫 화면에서 줄 길을 「봇 만들기」와 「에이전트에게 맡기기」 둘로 못박았기 때문이다.
 */
export const RAIL_ITEMS: readonly RailItem[] = [
  { id: "bench", label: "실험대", icon: "home", kind: "route", path: BENCH_PATH },
  {
    id: "research",
    label: "리서치",
    icon: "find",
    kind: "route",
    pending: "리서치 전체 폭 화면은 아직 없습니다.",
    dividerAfter: true,
  },
  { id: "bot", label: "봇", icon: "box", kind: "panel" },
  {
    id: "agent",
    label: "에이전트",
    icon: "robot",
    kind: "panel",
    expandable: true,
    pending: "에이전트 대화는 아직 없습니다. 긴 대화를 위해 폭만 620px 까지 넓힐 수 있습니다.",
  },
  {
    id: "trades",
    label: "거래 로그",
    icon: "bulletlist",
    kind: "panel",
    pending: "거래 로그 패널 내용은 아직 없습니다.",
  },
  {
    id: "rules",
    label: "내 기준",
    icon: "check",
    kind: "panel",
    pending: "내 기준 패널 내용은 아직 없습니다.",
    dividerAfter: true,
  },
  { id: "market", label: "시세", icon: "chart", kind: "route", path: MARKET_PATH },
  {
    id: "portfolio",
    label: "포트폴리오",
    icon: "money",
    kind: "panel",
    pending: "포트폴리오 패널 내용은 아직 없습니다.",
  },
  { id: "settings", label: "설정", icon: "preferences", kind: "route", path: ADMIN_PATH, footer: true },
] as const;
