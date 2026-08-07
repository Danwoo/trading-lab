// components/shared/ui/primitives/fieldState.ts
//
// `useFormState().getFieldProps(fieldName)` 계약을 프리미티브가 읽는 한 곳 (#341 ②).
//
// DevExtreme 시절엔 이 객체를 그대로 컴포넌트에 스프레드하면 라이브러리가 알아서
// `validationStatus`/`validationError` 를 읽어 빨간 테두리 + 메시지를 그렸다. 자체 프리미티브로
// 옮기면서 그 해석을 우리가 하게 됐는데, 프리미티브마다 따로 풀면 접근성 연결(`aria-invalid` ·
// `aria-describedby`)이 한 곳만 빠져도 조용히 죽는다 — TextBox 가 먼저 인라인으로 풀었던 것을
// (#391 B2) 여기로 올려 9개 프리미티브가 같은 코드를 쓰게 한다.
//
// `getFieldProps` 가 돌려주는 것 중 이 커널이 쓰는 키는 셋뿐이다:
//   - `validationStatus: "valid" | "invalid"`
//   - `validationError: { message } | { message }[]`
//   - `width: "100%"` — 호출부가 명시한 width 를 덮는다(DevExtreme 시절 스프레드 순서 보존)
// 나머지(`stylingMode` · `validationMessageMode`)는 네이티브 입력에 대응 개념이 없어 버린다.

export interface ResolvedFieldState {
  /** 서버 검증 실패 상태 — `aria-invalid` 와 빨간 테두리에 쓴다. */
  isInvalid: boolean;
  /** 첫 번째 에러 메시지. `isInvalid` 여도 메시지가 없을 수 있다. */
  errorMessage?: string;
  /** `getFieldProps().width` 가 호출부 `width` 를 덮은 최종값. */
  effectiveWidth?: number | string;
}

type GetFieldProps<K> = ((fieldName: K) => unknown) | undefined;

interface FieldPropsShape {
  validationStatus?: "valid" | "invalid";
  validationError?: { message?: string } | Array<{ message?: string }>;
  width?: number | string;
}

/**
 * `getFieldProps` 결과를 프리미티브가 쓰는 형태로 푼다.
 *
 * `fieldName` 이 `undefined` 면 호출하지 않는다 — 객체 state 폼 계약 밖(네이티브 폼 화면)에서는
 * 필드 키가 없고, 그 경우 검증 표시도 폼 쪽이 직접 한다(TextBox 의 「두 모드」 참조).
 */
export function resolveFieldState<K>(
  getFieldProps: GetFieldProps<K>,
  fieldName: K | undefined,
  width?: number | string,
): ResolvedFieldState {
  const raw = getFieldProps && fieldName !== undefined ? (getFieldProps(fieldName) as FieldPropsShape) : undefined;
  const isInvalid = raw?.validationStatus === "invalid";
  const error = raw?.validationError;
  const errorMessage = isInvalid ? (Array.isArray(error) ? error[0]?.message : error?.message) : undefined;
  return { isInvalid, errorMessage, effectiveWidth: raw?.width ?? width };
}
