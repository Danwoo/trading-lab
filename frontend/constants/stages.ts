/**
 * 제품이 스스로 말하는 **단계** — 지금 되는 것 / 다음 / 나중 / 지금은 안 하는 것.
 *
 * 이 레포는 「경로를 보여준다」를 원칙으로 세웠다 — 제품이 대신 판정하지 않고 남은 단계를
 * 다 보인다. 그 원칙은 한 화면 안에서만이 아니라 **제품 전체**에도 걸린다. 실험대 소개가
 * 「굴리는 자리」라고 말하는데 굴릴 길이 없으면, 받은 사람은 설정 어딘가에 실계좌 연결이
 * 있으리라 여기고 찾다가 없다는 것을 알게 된다 (#233).
 *
 * **정본은 레포 루트 `ROADMAP.md` 다.** 구간 이름(지금·다음·나중·하지 않는 것)도 그 문서의
 * 절 이름을 그대로 쓴다. 여기는 화면이 한 눈에 낼 만큼만 옮긴다 — 문서를 통째로 복제하면
 * 두 곳이 갈라지고, 갈라진 로드맵은 없느니만 못하다.
 */
export type StageState = "now" | "next" | "later" | "not-now";

export const STAGE_LABELS: Record<StageState, string> = {
  now: "지금",
  next: "다음",
  later: "나중",
  "not-now": "지금은 안 합니다",
};

export interface ProductStage {
  id: string;
  label: string;
  state: StageState;
  /** 왜 그 상태인지 — 조건이 붙은 것은 그 조건까지 적는다. */
  note?: string;
}

export const ROADMAP_URL = "https://github.com/Danwoo/trading-lab/blob/main/ROADMAP.md";

export const PRODUCT_STAGES: readonly ProductStage[] = [
  { id: "build", label: "봇 만들기", state: "now" },
  { id: "load", label: "시세 적재", state: "now" },
  { id: "verify", label: "과거로 검증", state: "next", note: "백테스트 엔진이 격자·곡선을 채웁니다" },
  { id: "paper", label: "모의계좌 주문", state: "next", note: "모의·실계좌가 같은 API 인 증권사부터" },
  { id: "live", label: "실주문 승격", state: "later", note: "백테스트·검증을 통과한 전략만" },
  {
    id: "unverified-live",
    label: "검증 없는 실주문 자동화",
    state: "not-now",
    note: "검증을 거치지 않은 전략으로 실계좌를 굴리지 않습니다",
  },
] as const;
