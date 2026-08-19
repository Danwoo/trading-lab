/**
 * `unavailable` 이 `reason` 을 타입으로 요구한다 — FR-021(이유 없는 빈 화면 금지)을
 * 컴파일 단계에서 강제하는 수단이다.
 */
export type Provenance =
  | { kind: "live" | "loaded"; source: string; asOf: string | null }
  /**
   * `note` 는 배지에 붙는 **짧은 꼬리표**(종목 티커 등)이고, `hint` 는 왜 임시인지와 무엇을
   * 하면 진짜 값이 오는지를 적은 **긴 문장**이다. 한 칸에 몰면 긴 문장이 헤더를 삼켜
   * 패널 제목까지 밀어낸다(실측) — 그래서 자리를 나눈다. 긴 쪽은 `PanelFrame` 이 안내줄로 낸다.
   */
  | { kind: "placeholder"; source: string; note?: string; hint?: string }
  /**
   * `because` 는 **배지가 무엇이라 부를지**를 정한다 — 사유 문장은 길어 배지에 못 넣고,
   * 문구를 보고 가르면 문구만 바뀌어도 판정이 조용히 갈린다.
   *
   * 안 붙이면 종전대로 「제공 안 됨」이다. `not-chosen` 은 「고르면 채워집니다」로 —
   * 첫 진입에서 이것이 화면을 덮으면 아직 아무것도 안 골랐을 뿐인데 고장 난 것처럼 보인다.
   */
  | { kind: "unavailable"; reason: string; because?: "not-chosen" };

export interface PanelData<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  provenance: Provenance;
}
