import { useState, useCallback, useRef } from "react";
import { createFieldChangeHandler, parseValidationErrors } from "@/utils/common/errors";
import { getValidationStatus, getValidationError } from "@/lib/grid/validation";
import { useUnsavedTabSignal } from "@/hooks/shared/useUnsavedTabSignal";

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
   * 「저장 안 한 입력이 있는가」의 기준선. 폼이 처음 받은 값이고, `resetForm` 과 저장 성공이
   * 여기를 다시 찍는다 — 그래야 저장한 뒤에도 표시가 남는 일이 없다.
   *
   * 이 판정을 여기에 두는 이유는 **폼 아홉 개가 전부 이 훅을 지나기 때문**이다. 화면마다 따로
   * 세면 하나를 빠뜨렸을 때 그 탭만 조용히 경고 없이 닫힌다 (#360).
   */
  const baseline = useRef(JSON.stringify(initialData ?? {}));
  useUnsavedTabSignal(JSON.stringify(formData) !== baseline.current);

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
        const saved = await onSubmit(formData as T);
        if (saved !== false) baseline.current = JSON.stringify(formData);
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
    baseline.current = JSON.stringify(newData ? { ...newData } : {});
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
