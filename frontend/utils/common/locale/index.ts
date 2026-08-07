// utils/common/locale/index.ts
// 앱 공통 언어(en/ko) 상태 + i18n 부트스트랩(Zod).
//
// - 상태(순수 함수): ./state.ts 로 분리(#345) — 부트스트랩 없이 상태만 쓰고 싶은 소비자
//   (예: utils/common/errors/apierrors.ts)는 "@/utils/common/locale/state" 를 직접 쓴다.
//   이 파일은 그 상태를 재노출하며 부트스트랩 side-effect 를 추가한다.
// - Zod 부트스트랩: ./zodBootstrap.ts 로 분리(#352) — Zod 설정만 필요한 소비자(schemas/* 가
//   거치는 lib/zod/helpers.ts)는 "@/utils/common/locale/zodBootstrap" 을 직접 쓴다.
//   이 파일은 그걸 재사용한다(ES 모듈 캐시로 apply() 는 1회만 실행).
// - **DevExtreme 메시지 로딩은 #341 로 사라졌다.** `loadMessages`/`locale()`(devextreme/
//   localization)로 ko 사전을 등록하던 부트스트랩과 ./ko/devextreme.ts·./en/devextreme.ts
//   사전이 함께 없어졌다 — DevExtreme 위젯이 하나도 남지 않아 번역할 대상이 없다. 그래서
//   `components/shared/ui/index.ts` 가 이 파일을 부수효과로 import 하던 줄도 함께 걷혔다
//   (배럴 하나가 화면 25개에 이 부트스트랩을 강제하던 통로 — #341 ②).
// - 언어별 메시지는 ./ko, ./en 폴더 (zod/apierrors). 언어 추가 = 폴더 + 매핑.
import "./zodBootstrap";

export type { AppLocale } from "./state";
export { APP_LOCALE_STORAGE_KEY, getAppLocale, setAppLocale } from "./state";
