/**
 * `unavailable` 이 `reason` 을 타입으로 요구한다 — FR-021(이유 없는 빈 화면 금지)을
 * 컴파일 단계에서 강제하는 수단이다.
 */
export type Provenance =
  | { kind: "live" | "loaded"; source: string; asOf: string | null }
  | { kind: "placeholder"; source: string; note?: string }
  | { kind: "unavailable"; reason: string };

export interface PanelData<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  provenance: Provenance;
}
