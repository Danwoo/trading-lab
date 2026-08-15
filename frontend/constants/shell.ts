import { ADMIN_PATH, BENCH_PATH, MARKET_PATH } from "@/constants/routes";

/** 아이콘 레일 폭 (화면 결정 §20 — 세로줄 하나로 유지, 넓은 사이드바는 쓰지 않는다). */
export const RAIL_WIDTH_PX = 46;

/** 패널 폭 (§20.2 — 보드를 덮지 않고 옆으로 민다. 에이전트 620px 토글은 §21.3, S3 소관). */
export const PANEL_WIDTH_PX = 372;

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
  /** 이 항목 다음에 구분선을 긋는다 */
  dividerAfter?: boolean;
  /** 레일 바닥에 붙인다 (위 묶음과 떨어뜨린다) */
  footer?: boolean;
}

/**
 * 레일 순서 — 화면 결정 §20.2 의 확정값이자 `bench-shell.html` 시안의 배치다.
 *
 * 실험대 · 리서치 / 봇 · 거래 로그 · 내 기준 / 시세 · 포트폴리오 / (바닥) 설정.
 * §20.2 본문은 리서치를 셋째 묶음에 적었는데, 같은 문서 §22.5 가 리서치를 **동등한 기둥**으로
 * 올리며 전체 폭 화면을 주기로 했다 — 시안(`bench-shell.html`)과 `#73` 계획의 열거가 둘 다
 * 실험대 옆이라 그쪽을 따랐다.
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
  { id: "bot", label: "봇", icon: "box", kind: "panel", pending: "봇 패널 내용은 아직 없습니다." },
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
