import { describe, expect, it } from "vitest";

import { getCodeName } from "@/utils/common/codeUtils";

const CODE_LIST = [
  { code: "01", code_nm: "정상" },
  { code: "02", code_nm: "중지" },
];

describe("getCodeName", () => {
  it("코드에 대응하는 코드명을 준다", () => {
    expect(getCodeName("01", CODE_LIST)).toBe("정상");
  });

  // 코드는 타입상 string 이지만 DB·API 에서 숫자로 오는 경우가 있어 양쪽을 String 으로 맞춘다.
  // 엄격 비교로 바꾸면 숫자 코드가 조용히 못 찾는 상태가 된다.
  it("숫자 코드도 문자열 코드와 매칭된다", () => {
    const numericCode = 1 as unknown as string;
    const numericList = [{ code: 1 as unknown as string, code_nm: "하나" }];
    expect(getCodeName(numericCode, [{ code: "1", code_nm: "하나" }])).toBe("하나");
    expect(getCodeName("1", numericList)).toBe("하나");
  });

  it("목록에 없으면 원래 코드를 그대로 준다 (빈 셀로 보이지 않게)", () => {
    expect(getCodeName("99", CODE_LIST)).toBe("99");
  });

  it("코드명이 비어 있으면 코드로 폴백한다", () => {
    expect(getCodeName("01", [{ code: "01", code_nm: "" }])).toBe("01");
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
    ["빈 문자열", ""],
  ])("코드가 %s 이면 빈 문자열", (_label, code) => {
    expect(getCodeName(code, CODE_LIST)).toBe("");
  });

  it.each([
    ["undefined", undefined],
    ["배열이 아닌 값", {} as unknown as typeof CODE_LIST],
  ])("코드 목록이 %s 이면 원래 코드를 준다", (_label, list) => {
    expect(getCodeName("01", list)).toBe("01");
  });
});
