// 화면 결정 §21.5 「절대 안 하는 것 — 조용히 낡은 값으로 계속 굴리는 것」의 계산부.
// 낡음 판정은 **날짜 경계**로 갈리므로 시각이 아니라 달력으로 재는지를 단언한다.
import { describe, expect, it } from "vitest";

import { describeStaleness, formatAsOfDay } from "@/lib/terminal/staleness";

/** 사용자 타임존 기준 그 날 정오 — 날짜 경계에서 흔들리지 않는 기준점 */
const noon = (iso: string) => new Date(`${iso}T12:00:00`).getTime();

describe("describeStaleness — 며칠 낡았나", () => {
  it("같은 날 적재본은 낡지 않았다 — 배지를 달지 않는다", () => {
    expect(describeStaleness("2026-08-15", noon("2026-08-15"))).toBeNull();
  });

  it("하루 전이면 「하루 낡음」 — §21.5 가 적은 문구 그대로", () => {
    expect(describeStaleness("2026-08-14", noon("2026-08-15"))).toEqual({ days: 1, label: "하루 낡음" });
  });

  it("이틀 이상은 날수로 적는다", () => {
    expect(describeStaleness("2026-08-06", noon("2026-08-15"))).toEqual({ days: 9, label: "9일 낡음" });
  });

  it("시각이 아니라 달력으로 잰다 — 23시간 차이라도 날짜가 다르면 하루다", () => {
    expect(describeStaleness("2026-08-14T23:30:00", noon("2026-08-15"))).toEqual({
      days: 1,
      label: "하루 낡음",
    });
  });

  it("몇 시간 차이라도 같은 날이면 낡지 않았다", () => {
    expect(describeStaleness("2026-08-15T01:00:00", noon("2026-08-15"))).toBeNull();
  });

  it("미래 날짜는 낡은 것이 아니다 — 시계가 어긋난 것이지 데이터 문제가 아니다", () => {
    expect(describeStaleness("2026-08-20", noon("2026-08-15"))).toBeNull();
  });

  it("기준 시각을 모르면 판정하지 않는다 — 모르는 것을 「최신」으로 읽지 않게 호출자에게 넘긴다", () => {
    expect(describeStaleness(null, noon("2026-08-15"))).toBeNull();
  });

  it("날짜로 못 읽는 값도 판정하지 않는다", () => {
    expect(describeStaleness("어제쯤", noon("2026-08-15"))).toBeNull();
  });
});

describe("formatAsOfDay — 배지에 쓰는 「08-06」", () => {
  it("연도를 뗀 월-일을 낸다", () => {
    expect(formatAsOfDay("2026-08-06")).toBe("08-06");
  });

  it("못 읽는 값은 null", () => {
    expect(formatAsOfDay("없음")).toBeNull();
  });
});
