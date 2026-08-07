/**
 * 상승/하락 의미 토큰(`--market-up`/`--market-down`)의 전환 기전 (#242 O3 착수 코멘트).
 * 한국식(적=상승·청=하락)과 미국식(녹=상승·적=하락)은 관습이 정반대라, 패널은 이 값을
 * 직접 참조하지 않고 CSS 변수만 참조한다 — 프리셋이 값을 채운다.
 *
 * O3 범위는 기전까지다: 토큰 + 전환 함수 + 지속. 프리셋을 고르는 설정 UI 는 만들지 않는다
 * (설정 표면이 아직 없다) — 이 모듈은 그 UI 가 생겼을 때 곧바로 붙일 수 있는 형태로만 존재한다.
 *
 * 색만으로 방향을 표시하지 않는다 — 소비자(패널)는 부호(+/−·▲/▼)를 항상 함께 그려야 한다.
 * 이 규약은 컴파일러가 강제할 수 없으니 여기 문서로 남긴다.
 */
export type MarketColorPreset = "kr" | "us";

/** 기본값은 한국식 — 앱이 한국어 우선이라는 것 자체가 결정이므로 명시한다. */
export const DEFAULT_MARKET_COLOR_PRESET: MarketColorPreset = "kr";

// "R G B" 채널 문자열(헤더 없음) — styles/globals.css 의 --market-up/--market-down 초기값과
// 같은 형식이어야 한다. Tailwind 가 이 값을 `rgb(var(--x) / <alpha-value>)` 로 소비해
// opacity modifier 를 지원한다(#313) — 여기서 hex 를 돌려주면 그 조합이 다시 조용히 깨진다.
const PRESET_VALUES: Record<MarketColorPreset, { up: string; down: string }> = {
  kr: { up: "240 70 90", down: "59 130 246" },
  us: { up: "34 197 94", down: "239 68 68" },
};

const STORAGE_KEY = "terminal-market-color-preset";

export function isMarketColorPreset(value: unknown): value is MarketColorPreset {
  return value === "kr" || value === "us";
}

/** 저장된 선호가 없거나 손상됐으면 `null` — 호출자가 `DEFAULT_MARKET_COLOR_PRESET` 으로 폴백한다. */
export function readStoredMarketColorPreset(): MarketColorPreset | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isMarketColorPreset(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function storeMarketColorPreset(preset: MarketColorPreset): void {
  try {
    localStorage.setItem(STORAGE_KEY, preset);
  } catch {
    // 사생활 보호 모드 등 저장소를 못 쓰는 환경 — 이번 세션에서만 적용된다
  }
}

export interface CssPropertyTarget {
  setProperty(name: string, value: string): void;
}

/** `target` 은 보통 `document.documentElement.style` — DOM 없이도 순수하게 테스트하기 위해 주입받는다. */
export function applyMarketColorPreset(preset: MarketColorPreset, target: CssPropertyTarget): void {
  const values = PRESET_VALUES[preset];
  target.setProperty("--market-up", values.up);
  target.setProperty("--market-down", values.down);
}
