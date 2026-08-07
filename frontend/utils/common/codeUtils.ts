// utils/common/codeUtils.ts

/**
 * 코드 리스트에서 코드명을 찾아 반환하는 함수
 * @param code 찾을 코드
 * @param codeList 코드 리스트 (array)
 * @returns 코드명 또는 원래 코드
 */
export const getCodeName = (
  code: string | undefined | null,
  codeList: Array<{ code: string; code_nm: string }> | undefined,
): string => {
  if (!code || !codeList || !Array.isArray(codeList)) {
    return code || "";
  }

  const codeItem = codeList.find((item) => String(item.code) === String(code));
  return codeItem?.code_nm || code;
};
