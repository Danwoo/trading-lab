/**
 * `unavailable` 이 `reason`(왜 비었나)과 `because`(어떤 종류의 빔인가)를 둘 다 타입으로
 * 요구한다 — FR-021(이유 없는 빈 화면 금지)을 컴파일 단계에서 강제하는 수단이다.
 */
export type Provenance =
  | { kind: "live" | "loaded"; source: string; asOf: string | null }
  /**
   * `note` 는 배지에 붙는 **짧은 꼬리표**(종목 티커 등)이고, `hint` 는 왜 임시인지와 무엇을
   * 하면 진짜 값이 오는지를 적은 **긴 문장**이다. 한 칸에 몰면 긴 문장이 헤더를 삼켜
   * 패널 제목까지 밀어낸다(실측) — 그래서 자리를 나눈다. 긴 쪽은 `PanelFrame` 이 안내줄로 낸다.
   */
  | { kind: "placeholder"; source: string; note?: string; hint?: string }
  | { kind: "unavailable"; reason: string; because: UnavailableBecause };

/**
 * **왜 비었나의 축** — 배지가 무엇이라 부를지를 정한다. 사유 문장은 길어 배지에 못 넣고,
 * 문구를 보고 가르면 문구만 바뀌어도 판정이 조용히 갈린다.
 *
 * - `not-chosen` 「고르면 채워집니다」 — 아직 아무것도 안 골랐다
 * - `checking` 「확인 중」 — 물어봤고 답을 기다린다. 아직 아무것도 주장하지 않는다
 * - `not-run` 「아직 실행 안 함」 — 돌릴 수 있는데 아직 안 돌렸다
 * - `run-failed` 「실행 실패」 — 돌렸고 실패했다. 「아직 안 돌렸다」와 할 일이 다르다
 * - `empty` 「대상 없음」 — 읽었고 0건이었다
 * - `unreadable` 「못 읽음」 — 못 읽었다. 0건인지 아닌지 **모른다**
 * - `no-source` 「제공 안 됨」 — 줄 소스가 없다. 사용자가 할 수 있는 것이 없다
 *
 * **생략할 수 없다.** 기본값을 두면 새로 생기는 자리가 조용히 「제공 안 됨」이 되어,
 * 동작하는 자리에 「제공 안 됨」이 붙는 일이 되풀이된다(#284).
 */
export type UnavailableBecause =
  | "not-chosen"
  | "checking"
  | "not-run"
  | "run-failed"
  | "empty"
  | "unreadable"
  | "no-source";

export interface PanelData<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  provenance: Provenance;
}
