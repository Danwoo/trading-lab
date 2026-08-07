import { PanelUnavailable } from "./PanelUnavailable";

/**
 * 스크리너 결과 탭 — 스크리너 테이블·서비스가 아직 없다(#326 이슈, `screener` grep 0 hit).
 * 가짜 종목 목록을 만드는 대신 O3 의 출처 표시 장치(`PanelUnavailable`)를 그대로 재사용해
 * 이유와 함께 빈 상태를 보여준다(NFR-001·SC-005).
 */
export function ScreenerTab() {
  return (
    <PanelUnavailable reason="스크리너 결과가 아직 제공되지 않습니다 — 스크리너 테이블과 서비스가 아직 없습니다." />
  );
}
