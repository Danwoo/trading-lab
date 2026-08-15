/**
 * #150 B0 — 전략 선언에서 온 폼을 화면이 어떻게 먹는지 고정한다.
 *
 * 백엔드가 이미 「전략을 더해도 화면 코드를 안 고친다」를 테스트로 보였다
 * (backend-service/tests/test_strategy_contract.py). 여기서는 **프론트 쪽 계약**을 못 박는다:
 * 화면은 `control` 세 종만 알고, 폼을 열자마자 유효한 값이 채워져 있어야 한다
 * (실험대 스펙 §8.6.1 — 폼이 언제나 지금 값을 보여줘야 대화가 그것을 검증할 수 있다).
 */
import { describe, expect, it } from "vitest";
import { COMBINE_RULES, BOT_ROLES, PARAM_SOURCES, UNIVERSE_KINDS, StrategyForm } from "@/schemas/bot/bot";
import { defaultParams } from "@/services/bot/botService";

/** 화면이 그릴 줄 아는 컨트롤 — 이 집합이 늘면 폼 렌더러도 같이 고쳐야 한다. */
const KNOWN_CONTROLS = new Set(["number", "select", "toggle"]);

const form: StrategyForm = {
  key: "ma_pullback",
  name: "이동평균 눌림목",
  summary: "평균선 아래로 눌린 자리",
  timeframe: "1d",
  fields: [
    { name: "ma_period", label: "평균선 기간", control: "number", default: 20, min: 5, max: 120, step: 1, unit: "일" },
    {
      name: "pullback_pct",
      label: "눌림 깊이",
      control: "number",
      default: 3.0,
      min: 0.5,
      max: 15,
      step: 0.5,
      unit: "%",
    },
    { name: "recover_confirm", label: "회복 확인", control: "toggle", default: true },
    {
      name: "measure",
      label: "무엇으로 재나",
      control: "select",
      default: "close",
      options: [
        { value: "close", label: "종가" },
        { value: "high", label: "고가" },
      ],
    },
  ],
};

describe("전략 폼 — 선언이 화면을 만든다", () => {
  it("폼을 열자마자 모든 파라미터가 선언한 기본값으로 채워진다", () => {
    expect(defaultParams(form)).toEqual({
      ma_period: 20,
      pullback_pct: 3.0,
      recover_confirm: true,
      measure: "close",
    });
  });

  it("필드가 0개인 전략도 빈 객체를 돌려준다 (파라미터 없는 전략이 화면을 깨지 않는다)", () => {
    expect(defaultParams({ ...form, fields: [] })).toEqual({});
  });

  it("화면이 아는 control 세 종 밖이 없다 — 이게 깨지면 폼 렌더러를 같이 고쳐야 한다", () => {
    expect(form.fields.length).toBeGreaterThan(0);
    for (const field of form.fields) {
      expect(KNOWN_CONTROLS.has(field.control), `모르는 control: ${field.control}`).toBe(true);
    }
  });
});

describe("어휘 — 백엔드 CHECK 제약과 같아야 한다", () => {
  // 한쪽만 늘리면 저장이 500 으로 터진다. 백엔드는 alembic 0014 의 CHECK 와 스키마·서비스를
  // test_bot_schema_sql_consistency.py 로 대조하고, 프론트 몫이 이 단언이다.
  it("어휘가 비어 있지 않다 (0건을 훑고 초록이 되는 것을 막는다)", () => {
    for (const vocabulary of [COMBINE_RULES, UNIVERSE_KINDS, BOT_ROLES, PARAM_SOURCES]) {
      expect(vocabulary.length).toBeGreaterThan(0);
    }
  });

  it("어휘 값이 백엔드가 선언한 것과 글자까지 같다", () => {
    expect([...COMBINE_RULES]).toEqual(["AND", "OR", "SCORE"]);
    expect([...UNIVERSE_KINDS]).toEqual(["POOL", "WATCHLIST", "LIST"]);
    expect([...BOT_ROLES]).toEqual(["READONLY", "PROPOSE", "EXECUTE"]);
    expect([...PARAM_SOURCES]).toEqual(["USER", "AI_SUGGESTED"]);
  });
});
