import { useState, useCallback } from "react";
import { createFieldChangeHandler, parseValidationErrors } from "@/utils/common/errors";
import { getValidationStatus, getValidationError } from "@/lib/grid/validation";

/**
 * DevExtreme 폼 컴포넌트와 연동되는 폼 상태 및 유효성 검사 관리 훅
 *
 * 폼 데이터, 필드별 에러 상태를 관리하며 서버 유효성 검사 에러를 자동 처리합니다.
 */
export function useFormState<T>(initialData: Partial<T>) {
  const [formData, setFormData] = useState<Partial<T>>(() => ({ ...initialData }));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * 필드 값 변경 시 폼 데이터와 에러 상태를 함께 갱신
   */
  const handleFieldChange = useCallback(
    createFieldChangeHandler(setFormData, fieldErrors, setFieldErrors),
    [fieldErrors], // 의존성 추가
  );

  /**
   * DevExtreme 컴포넌트용 공통 속성 생성
   * validation 상태, 에러 메시지, 스타일 등을 자동 설정
   */
  const getFieldProps = useCallback(
    (fieldName: string) => ({
      validationStatus: getValidationStatus(fieldErrors, fieldName) as "valid" | "invalid",
      validationError: getValidationError(fieldErrors, fieldName),
      validationMessageMode: "always" as const,
      stylingMode: "outlined" as const,
      width: "100%",
    }),
    [fieldErrors],
  );

  /**
   * 폼 제출 처리
   * 서버 validation 에러(422) 발생 시 에러 상태 자동 갱신
   */
  const handleSubmit = useCallback(
    async (onSubmit: (data: T) => Promise<boolean>): Promise<void> => {
      setIsSubmitting(true);
      setFieldErrors({});
      try {
        await onSubmit(formData as T);
      } catch (error: any) {
        if (error?.response?.status === 422) {
          const validationErrors = parseValidationErrors(error.response.data);
          setFieldErrors(validationErrors);
        } else {
          throw error;
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [formData],
  );

  /**
   * 폼 데이터 수동 리셋 함수 (모달 열기/닫기 시 사용)
   */
  const resetForm = useCallback((newData: Partial<T>) => {
    setFormData(newData ? { ...newData } : {});
    setFieldErrors({});
    setIsSubmitting(false);
  }, []);

  return {
    formData,
    isSubmitting,
    handleFieldChange,
    getFieldProps,
    handleSubmit,
    resetForm,
  };
}
