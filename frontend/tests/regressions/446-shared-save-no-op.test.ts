// @vitest-environment node
//
// #446 F33 (후속) — 「안 바뀐 저장이 「변경되었습니다」라고 하지 않는다」를 **공용 저장 경로**에
// 건다.
//
// 앞선 수정(#460)은 마이페이지 한 화면만 고쳤다. 그런데 거의 모든 CRUD 화면은
// `DetailPanel`·`DetailGridPanel` 의 저장을 지나고, 그쪽은 바뀐 것이 없어도 `update` 를 부르고
// 「수정이 완료되었습니다」를 띄웠다 — 예외를 고치고 규칙을 남긴 꼴이었다.
//
// **이 판정은 한쪽으로만 틀려야 한다.** 「안 바뀌었다」를 잘못 말하면 사용자의 진짜 편집이
// 저장되지 않고 사라진다 — 지금의 거짓말보다 나쁘다. 그래서 아래 절반은 「확실하지 않으면
// 저장한다」를 단언한다.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { isUnchanged, NOTHING_CHANGED } from "@/utils/common/form/unchanged";

describe("안 바뀐 저장을 가른다", () => {
  it("모든 칸이 같으면 안 바뀐 것이다", () => {
    expect(isUnchanged({ name: "삼성전자", memo: "장기" }, { name: "삼성전자", memo: "장기", rn: 1 })).toBe(true);
  });

  it("한 칸이라도 다르면 바뀐 것이다", () => {
    expect(isUnchanged({ name: "삼성전자", memo: "단기" }, { name: "삼성전자", memo: "장기" })).toBe(false);
  });

  it('빈 칸의 두 표기(null·undefined·"")는 같은 것으로 본다 — 폼은 "", 서버는 null 을 준다', () => {
    expect(isUnchanged({ memo: "" }, { memo: null })).toBe(true);
    expect(isUnchanged({ memo: "" }, { memo: undefined })).toBe(true);
    expect(isUnchanged({ memo: null }, { memo: "" })).toBe(true);
  });

  it("폼이 담지 않은 칸은 보지 않는다 — 이 저장이 건드리지 않는 칸이다", () => {
    expect(isUnchanged({ name: "A" }, { name: "A", mod_dt: "2026-09-14", rn: 3 })).toBe(true);
  });
});

describe("확실하지 않으면 저장한다 — 판정은 한쪽으로만 틀린다", () => {
  it("숫자와 문자열을 같다고 하지 않는다", () => {
    expect(isUnchanged({ qty: 5 }, { qty: "5" })).toBe(false);
    expect(isUnchanged({ use_at: true }, { use_at: "true" })).toBe(false);
  });

  it("현재 값을 모르면 저장한다", () => {
    expect(isUnchanged({ name: "A" }, null)).toBe(false);
    expect(isUnchanged({ name: "A" }, undefined)).toBe(false);
  });

  it("현재 레코드에 없는 칸을 보내면 저장한다", () => {
    expect(isUnchanged({ newField: "A" }, { name: "A" })).toBe(false);
  });

  it("원시값이 아닌 것이 섞이면 저장한다 — 비교할 수 없다", () => {
    expect(isUnchanged({ tags: ["a"] }, { tags: ["a"] })).toBe(false);
    expect(isUnchanged({ meta: { a: 1 } }, { meta: { a: 1 } })).toBe(false);
    expect(isUnchanged({ at: new Date(0) }, { at: new Date(0) })).toBe(false);
  });

  it("빈 폼을 「안 바뀜」으로 접지 않는다", () => {
    expect(isUnchanged({}, { name: "A" })).toBe(false);
  });

  it("비교 대상이 객체가 아니면 저장한다", () => {
    expect(isUnchanged("A", "A")).toBe(false);
    expect(isUnchanged([1], [1])).toBe(false);
  });
});

describe("공용 저장 경로가 이 판정을 실제로 쓴다", () => {
  // 헬퍼만 초록이고 화면이 안 부르면 아무것도 안 바뀐다 — 부르는 자리를 소스로 확인한다.
  const read = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

  const PANELS = ["components/shared/DataPanel/DetailPanel.tsx", "components/shared/DataPanel/DetailGridPanel.tsx"];

  it("두 공용 패널이 모두 판정을 거쳐 update 를 부른다", () => {
    expect(PANELS.length).toBeGreaterThan(0);
    for (const panel of PANELS) {
      const source = read(panel);
      expect(source, `${panel} 이 isUnchanged 를 부르지 않는다`).toContain("isUnchanged(");
      expect(source, `${panel} 이 안 바뀐 저장에 낼 말을 공용 상수로 쓰지 않는다`).toContain("NOTHING_CHANGED");
    }
  });

  // **부르기만 하면 되는 것이 아니라 무엇과 비교하는지가 판정을 가른다.** 기준선이 폼이
  // 보여준 값이 아니면, 남의 탭이 바꾼 값을 원래대로 되돌리는 **진짜 편집**이 「안 바뀜」으로
  // 삼켜진다 — 이 판정이 틀려서는 안 되는 바로 그 방향이다. 종전 단언은 `isUnchanged(` 만
  // 봐서 인자가 틀려도 초록이었다(실제로 그랬다).
  it("비교 기준은 폼이 실제로 보여준 값이다 — 낡은 prop 이 아니다", () => {
    const detail = read("components/shared/DataPanel/DetailPanel.tsx");
    // 폼 초기값과 판정 기준선이 같은 것을 가리켜야 한다.
    expect(detail, "폼이 currentData 로 초기화되지 않는다면 이 그물의 전제가 바뀐 것이다").toMatch(
      /initialData=\{.*currentData/,
    );
    expect(detail, "판정 기준선이 폼 초기값(currentData)이 아니다").toContain("isUnchanged(submitData, currentData)");

    const grid = read("components/shared/DataPanel/DetailGridPanel.tsx");
    expect(grid, "수정 모달이 selectedData 로 초기화되지 않는다면 전제가 바뀐 것이다").toContain(
      "useDetailModal(selectedData)",
    );
    expect(grid, "판정 기준선이 모달 초기값(selectedData)이 아니다").toContain("isUnchanged(data, selectedData)");
  });

  it("안 바뀐 저장에 내는 말이 「완료」라고 하지 않는다", () => {
    expect(NOTHING_CHANGED).not.toMatch(/완료|변경되었습니다|저장되었습니다/);
  });
});

// 남의 탭이 값을 바꾼 뒤(#446 B-27 상황) **원래대로 되돌리는 편집**이 삼켜지는지 —
// 이 판정이 틀려서는 안 되는 유일한 방향이다. 헬퍼를 화면이 쓰는 두 기준선으로 각각 태워
// 무엇이 갈리는지 눈으로 보인다.
describe("남의 변경을 되돌리는 편집은 저장된다", () => {
  const propSnapshot = { memo: "A", name: "삼성전자" }; // 목록이 받아 온 낡은 스냅샷
  const freshlyLoaded = { memo: "B", name: "삼성전자" }; // 수정을 누를 때 다시 불러온 최신
  const submitted = { memo: "A", name: "삼성전자" }; // 사용자가 B 를 A 로 되돌렸다

  it("폼이 보여준 값과 다르므로 저장한다", () => {
    expect(isUnchanged(submitted, freshlyLoaded)).toBe(false);
  });

  it("낡은 prop 을 기준으로 삼으면 진짜 편집이 삼켜진다 — 그래서 기준선이 중요하다", () => {
    expect(isUnchanged(submitted, propSnapshot)).toBe(true);
  });
});
