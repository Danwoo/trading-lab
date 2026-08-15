/**
 * 관리 셸의 진입점 — 라우트를 존재하게 하는 것이 이 파일의 전부다.
 *
 * MDI 섀시(`layout.tsx`)는 메인 프레임에서 `children` 을 그리지 않는다. 화면은 전부 탭
 * (iframe)이 그리고, 탭이 하나도 없을 때 무엇을 보여줄지는 `GlobalTabs` 가 정한다. 그래서
 * 여기서 그릴 것이 없다 — 이 파일이 없으면 `/admin` 이 404 가 되어 레일의 「설정」이 막힌다.
 */
export default function Page() {
  return null;
}
