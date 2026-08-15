/**
 * 제품 셸의 자리와 레일 구성 — 화면 설계 §20.2(레일 순서·이동 규칙)와 §21.6(폭)이 정본이다.
 *
 * 셸은 둘이다. **제품 셸**(`app/(product)/`)은 46px 레일 + 본문 + 372px 패널 자리를 갖고,
 * **관리 셸**(`app/(main)/admin/`)은 MDI 탭 섀시를 갖는다. 화면 전환은 「시세」와 `/admin`
 * 둘뿐이라는 §20.2 의 결정이 이 파일의 목적지 세 개로 나타난다.
 */

/** 아이콘 레일 폭 (§20.2). */
export const RAIL_WIDTH_PX = 46;

/** 패널 자리 폭 (§20.2 — 보드를 덮지 않고 옆으로 민다). */
export const PANEL_WIDTH_PX = 372;

/** 실험대 — 홈이자 로그인 후 착지점 (§20.2 「㉮ 실험대가 홈」). */
export const BENCH_PATH = "/bench";

/** 시세 — 전체 폭 목적지. 봇과 무관하게 종목을 볼 때 쓴다 (§20.3). */
export const QUOTES_PATH = "/terminal";

/** 관리 화면 — MDI 탭 섀시의 진입점 (§20.2 「MDI 탭은 `/admin` 에만 남긴다」). */
export const ADMIN_HOME_PATH = "/admin";

/** 제품 셸이 소유하는 경로. 미들웨어 matcher 와 이 목록이 어긋나면 보호가 조용히 빠진다. */
export const PRODUCT_PATHS = [BENCH_PATH, QUOTES_PATH] as const;

/**
 * 레일 항목의 세 갈래.
 *
 * - `destination` — 전체 폭 화면으로 이동한다 (§22.5 의 전체 폭 목록)
 * - `panel` — 372px 패널을 열고 닫는다. **보드는 안 바뀐다** (§20.2 이동 규칙 1행)
 * - `pending` — 자리는 확정됐고 화면이 아직 없다. 눌러도 아무 일도 일어나지 않으며 그 사실을
 *   레일이 말한다 (숨기면 확정된 순서가 화면에서 사라진다)
 */
export type RailItem =
  | { kind: "destination"; id: string; label: string; icon: string; path: string }
  | { kind: "panel"; id: string; label: string; icon: string; comingUp: string }
  | { kind: "pending"; id: string; label: string; icon: string; note: string };

/**
 * 레일 순서 — §20.2 의 확정값에 §22.4(리서치를 맨 위 두 번째로 승격)를 적용한 것.
 * `null` 은 구분선이다.
 */
export const RAIL_ITEMS: readonly (RailItem | null)[] = [
  { kind: "destination", id: "bench", label: "실험대", icon: "home", path: BENCH_PATH },
  { kind: "pending", id: "research", label: "리서치", icon: "doc", note: "리서치 화면은 아직 없습니다" },
  { kind: "panel", id: "bots", label: "봇", icon: "product", comingUp: "봇 목록과 상세(조건·검진·운용)" },
  { kind: "panel", id: "trades", label: "거래 로그", icon: "bulletlist", comingUp: "거래 한 건과 그 구간의 차트" },
  { kind: "panel", id: "rules", label: "내 기준", icon: "check", comingUp: "어느 정도면 쓸 만한가 — 내가 적은 잣대" },
  null,
  { kind: "destination", id: "quotes", label: "시세", icon: "chart", path: QUOTES_PATH },
  { kind: "pending", id: "portfolio", label: "포트폴리오", icon: "box", note: "포트폴리오 화면은 아직 없습니다" },
] as const;

/** 레일 맨 아래에 고정되는 항목 (§20.2 의 마지막 칸). */
export const RAIL_FOOTER_ITEMS: readonly RailItem[] = [
  { kind: "destination", id: "admin", label: "설정", icon: "preferences", path: ADMIN_HOME_PATH },
] as const;
