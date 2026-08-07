// utils/common/locale/zodBootstrap.ts
// Zod 에러 메시지 i18n 부트스트랩 — devextreme 의존 없는 순수 side-effect (#352).
//
// index.ts 는 DevExtreme 메시지 로드 + Zod 설정을 한 파일에서 같이 부트스트랩했다. 그런데
// lib/zod/helpers.ts(모든 schemas/* 가 거치는 공용 헬퍼)가 Zod 설정만 필요한데도 index.ts 를
// 부작용 import 해, devextreme/localization 을 스키마 전체에 전이로 물렸다(#345 가 고친
// utils/common/errors 경로와 같은 클래스의 결함, 다른 목적지행 경로).
//
// 이 파일은 Zod 설정 적용만 분리한다 — index.ts 는 이 파일을 재사용(re-import)해 DevExtreme
// 부트스트랩과 합쳐 제공하고(components/shared/ui/index.ts 등 DevExtreme 도 쓰는 소비자용),
// Zod 만 필요한 소비자(lib/zod/helpers.ts)는 이 파일을 직접 부작용 import 한다. ES 모듈은
// 캐시되므로 두 경로 모두에서 로드돼도 apply() 는 1회만 실행된다.
import { type AppLocale, getAppLocale } from "./state";
import * as koZod from "./ko/zod";
import * as enZod from "./en/zod";

const ZOD_BY_LOCALE: Record<AppLocale, { apply: () => void }> = { ko: koZod, en: enZod };

ZOD_BY_LOCALE[getAppLocale()].apply();
