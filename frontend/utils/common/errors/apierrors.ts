// utils/common/errors/apierrors.ts
// #345 — 상태만 필요하므로 부트스트랩(devextreme/localization)이 없는 순수 모듈에서 가져온다.
// "@/utils/common/locale" 에서 가져오면 이 파일(→ utils/common/errors, 21개 파일이 쓰는 공용)이
// devextreme 을 전이로 물어 터미널 진입점 전이 의존 그물에 걸렸다.
import { getAppLocale, type AppLocale } from "@/utils/common/locale/state";
import * as ko from "@/utils/common/locale/ko/apierrors";
import * as en from "@/utils/common/locale/en/apierrors";

// 언어별 메시지 테이블 (locale/ko.ts, locale/en.ts) — 로직만 여기에.
const LOCALES: Record<AppLocale, typeof ko> = { ko, en };

/**
 * detail 배열의 Prisma 에러를 type(실제 코드 P#### / prisma_*)으로 번역. 첫 매칭 반환, 없으면 null.
 * Zod/Pydantic 검증 에러는 type 이 PRISMA_ERROR_MAP 에 없어 null → 호출자가 msg(구체 메시지) 사용.
 */
function translatePrismaErrors(errors: any[], L: typeof ko): string | null {
  for (const error of errors) {
    const translated = error?.type ? L.PRISMA_ERROR_MAP.get(error.type) : undefined;
    if (translated) return translated;
  }
  return null;
}

/**
 * API 에러를 사용자 친화적인 메시지로 변환. 클라이언트 폴백은 현재 언어(getAppLocale)에 따름.
 */
export function getApiErrorMessage(error: any): string {
  const L = LOCALES[getAppLocale()];

  if (error?.response?.data) {
    const errorData = error.response.data;

    // FastAPI detail 처리 (문자열과 배열 모두 지원)
    if (errorData.detail) {
      // detail이 문자열인 경우 (FastAPI 단순 에러 — 서버 제공 메시지)
      if (typeof errorData.detail === "string") {
        return errorData.detail;
      }

      // detail이 배열인 경우 (Pydantic 유효성 검사 에러 + Prisma 에러)
      if (Array.isArray(errorData.detail)) {
        // Prisma 에러 메시지 우선 처리
        const prismaMessage = translatePrismaErrors(errorData.detail, L);
        if (prismaMessage) return prismaMessage;

        // detail 배열의 첫 번째 에러 메시지 처리 (서버 제공)
        if (errorData.detail.length > 0) {
          const firstError = errorData.detail[0];
          if (firstError.msg) return firstError.msg;
        }

        // 상태 코드에 따른 기본 메시지
        const statusCode = error.response.status;
        return L.STATUS_MESSAGES[statusCode] || L.FALLBACK.processing;
      }
    }

    // 일반적인 에러 메시지 처리 (error, message 필드 — 서버 제공)
    if (errorData.error || errorData.message) {
      return errorData.error || errorData.message;
    }
  }

  // HTTP 상태 코드별 기본 메시지
  const statusCode = error?.response?.status;
  if (statusCode && L.STATUS_MESSAGES[statusCode]) {
    return L.STATUS_MESSAGES[statusCode];
  }

  // axios 에러 아님 (네트워크 오류 또는 코드 버그) — dev 에선 원본 로깅해 "네트워크" 토스트로 숨는 것 방지
  if (process.env.NODE_ENV === "development") {
    console.error("[getApiErrorMessage] 미인식 에러 (네트워크 또는 코드 버그):", error);
  }

  // 네트워크 연결 오류 등
  if (error?.message) {
    return L.FALLBACK.network;
  }

  return L.FALLBACK.unknown;
}
