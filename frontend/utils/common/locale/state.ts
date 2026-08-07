// utils/common/locale/state.ts
// 앱 공통 언어(en/ko) 상태 — 순수 함수만. devextreme·zod 부트스트랩 side-effect 는 없다.
//
// #345 — utils/common/locale/index.ts 에 상태 함수와 부트스트랩(devextreme/localization 포함)이
// 한 파일에 같이 있어서, 상태만 필요한 소비자(예: utils/common/errors/apierrors.ts, 21개 파일이
// 쓰는 공용 에러 처리)도 devextreme 을 전이로 물었다 — 크래시와는 무관했지만(#345 조사에서 확인)
// 터미널 진입점 전이 의존 그물(check-terminal-devextreme-transitive.js)이 계속 알려진 hit 로
// 추적해야 했다. 이 파일은 상태만 분리해 그 전이를 끊는다.
//
// index.ts 는 이 파일을 재노출하며 부트스트랩 side-effect 를 그대로 유지한다 — devextreme 부트
// 스트랩이 실제로 필요한 소비자(components/shared/ui/index.ts, lib/zod/helpers.ts)는 계속
// "@/utils/common/locale" 를 쓰면 된다. 상태만 필요하면 이 파일("@/utils/common/locale/state")을
// 직접 쓴다.

export type AppLocale = "ko" | "en";
export const APP_LOCALE_STORAGE_KEY = "app-locale";

/** 현재 활성 언어 (기본 ko). SSR 안전. */
export function getAppLocale(): AppLocale {
  if (typeof window === "undefined") return "ko";
  return window.localStorage.getItem(APP_LOCALE_STORAGE_KEY) === "en" ? "en" : "ko";
}

/** 언어 전환: 저장 후 새로고침 (DevExtreme 위젯·Zod config 는 로드 시 locale 을 읽으므로 reload 로 재적용). */
export function setAppLocale(next: AppLocale): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(APP_LOCALE_STORAGE_KEY, next);
  window.location.reload();
}
