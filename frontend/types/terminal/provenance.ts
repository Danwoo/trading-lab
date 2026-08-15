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
  | { kind: "unavailable"; reason: string };

export interface PanelData<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  provenance: Provenance;
}
