// utils/common/errors/forms.ts

import type { Dispatch, SetStateAction } from "react";
import { removeFieldError } from ".";

/**
 * DevExtreme Form 용 validation 에러 파싱.
 * Zod 가 primary validation 이므로 백엔드 에러 도달 = Zod 스키마 gap (버그). raw 메시지 그대로 노출해 인지 유도.
 */
export const parseValidationErrors = (errorResponse: any): Record<string, string> => {
  const errors: Record<string, string> = {};

  if (errorResponse?.detail && Array.isArray(errorResponse.detail)) {
    errorResponse.detail.forEach((error: any) => {
      if (error.loc && Array.isArray(error.loc) && error.loc.length > 0) {
        const fieldName = error.loc[error.loc.length - 1];
        errors[fieldName] = error.msg || "validation error";
      }
    });
  }

  return errors;
};

/**
 * 필드 값 변경 핸들러 생성 함수
 * 필드 값 업데이트와 동시에 해당 필드의 에러 상태 정리
 */
export const createFieldChangeHandler = <T>(
  setFormData: Dispatch<SetStateAction<Partial<T>>>,
  fieldErrors: Record<string, string>,
  setFieldErrors: Dispatch<SetStateAction<Record<string, string>>>,
) => {
  return (field: keyof T, value: any) => {
    // 폼 데이터 업데이트
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));

    // 해당 필드의 에러가 있다면 제거
    if (fieldErrors[field as string]) {
      setFieldErrors((prev) => removeFieldError(prev, field as string));
    }
  };
};
