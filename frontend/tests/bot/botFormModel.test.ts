/**
 * #150 B1 — 봇 폼의 순수 부분을 검증한다 (렌더 없이).
 *
 * 화면 회귀 중 **말없이 틀리는 것**만 여기서 잡는다:
 * - 저장 본문이 백엔드 계약을 벗어나면 저장이 4xx/500 으로 터진다.
 * - 선택지 어휘가 스키마(=DB CHECK 제약)와 어긋나면 저장이 500 이다.
 * - 저장한 봇을 다시 열었을 때 조건이 그대로 돌아오지 않으면 마일스톤 2 의 완료 조건이 깨진다.
 */
import { describe, expect, it } from "vitest";
import { BotCreateInSchema, BOT_ROLES, COMBINE_RULES, UNIVERSE_KINDS } from "@/schemas/bot/bot";
import {
  BOT_ROLE_ITEMS,
  COMBINE_RULE_ITEMS,
  NEW_BOT_DRAFT,
  UNIVERSE_KIND_ITEMS,
  fieldNameFromServerError,
  newStrategyDraft,
  toCreatePayload,
  toDraft,
} from "@/components/features/Bot/botFormModel";
import type { BotDetailOut, StrategyForm } from "@/schemas/bot/bot";

const FORM: StrategyForm = {
  key: "ma_pullback",
  name: "이동평균 눌림목",
  summary: null,
  timeframe: "1d",
  fields: [
    { name: "period", label: "평균선 기간", control: "number", default: 20, min: 5, max: 120, step: 1 },
    { name: "depth", label: "눌림 깊이", control: "number", default: 3 },
    { name: "confirm", label: "회복 확인", control: "toggle", default: true },
  ],
};

describe("봇 폼 — 저장 본문", () => {
  it("전략 기본값으로 채운 새 봇이 백엔드 스키마를 그대로 통과한다", () => {
    const payload = toCreatePayload({ ...NEW_BOT_DRAFT, bot_nm: "첫 봇" }, [newStrategyDraft(FORM)]);
    const parsed = BotCreateInSchema.safeParse(payload);
    expect(parsed.success, JSON.stringify(parsed.error?.issues)).toBe(true);
    expect(payload.strategies[0].params).toEqual({ period: 20, depth: 3, confirm: true });
  });

  it("빈 설명은 아예 안 보낸다 — 「지웠다」와 「안 적었다」가 같아지면 안 된다", () => {
    const payload = toCreatePayload({ ...NEW_BOT_DRAFT, bot_nm: "첫 봇", bot_desc: "   " }, [newStrategyDraft(FORM)]);
    expect(payload.bot_desc).toBeUndefined();
  });

  it("손댄 설정에만 출처가 실린다 (§8.6.3)", () => {
    const draft = newStrategyDraft(FORM);
    const edited = { ...draft, params: { ...draft.params, period: 60 }, paramSources: { period: "USER" as const } };
    const payload = toCreatePayload({ ...NEW_BOT_DRAFT, bot_nm: "첫 봇" }, [edited]);
    expect(payload.strategies[0].param_sources).toEqual({ period: "USER" });
  });

  it("새 봇은 보기 전용으로 시작한다 — 켠 적 없는 권한을 봇이 갖지 않는다", () => {
    expect(NEW_BOT_DRAFT.bot_role).toBe("READONLY");
  });
});

describe("봇 폼 — 선택지 어휘", () => {
  it("대상 종목·조건 결합은 스키마 어휘를 전부 덮는다", () => {
    expect(UNIVERSE_KIND_ITEMS.map((item) => item.value).sort()).toEqual([...UNIVERSE_KINDS].sort());
    expect(COMBINE_RULE_ITEMS.map((item) => item.value).sort()).toEqual([...COMBINE_RULES].sort());
  });

  it("역할은 스키마의 부분집합이고, 실주문(EXECUTE)은 의도적으로 빠져 있다", () => {
    const offered = BOT_ROLE_ITEMS.map((item) => item.value);
    expect(offered.every((value) => (BOT_ROLES as readonly string[]).includes(value))).toBe(true);
    expect(offered, "주문 엔진이 없는데 EXECUTE 를 고르게 하면 「켰으니 돈다」로 읽힌다").not.toContain("EXECUTE");
    expect(offered.length).toBeGreaterThan(0);
  });
});

describe("봇 폼 — 다시 열기", () => {
  it("저장된 봇의 조건이 폼 상태로 그대로 돌아온다 (M2 완료 조건)", () => {
    const saved = {
      bot_id: 1,
      bot_nm: "대형주 20일선 눌림목",
      bot_desc: "눌림목",
      combine_rule: "OR",
      universe_kind: "POOL",
      bot_role: "PROPOSE",
      alloc_per_symbol: 5,
      max_positions: 10,
      stop_loss_pct: 7,
      take_profit_pct: 15,
      max_trades_per_day: 3,
      use_at: "Y",
      param_sources: {},
      strategies: [],
    } as unknown as BotDetailOut;

    const draft = toDraft(saved);
    // 필드를 하나라도 빠뜨리면 그 조건이 화면에서 조용히 사라진다 — 전수로 대조한다.
    expect(draft).toEqual({
      bot_nm: "대형주 20일선 눌림목",
      bot_desc: "눌림목",
      combine_rule: "OR",
      universe_kind: "POOL",
      bot_role: "PROPOSE",
      alloc_per_symbol: 5,
      max_positions: 10,
      stop_loss_pct: 7,
      take_profit_pct: 15,
      max_trades_per_day: 3,
    });
    expect(Object.keys(draft).sort()).toEqual(Object.keys(NEW_BOT_DRAFT).sort());
  });
});

// F18 — 서버(#345)가 「라벨」로 짚어 준 오류를 그 칸으로 되돌린다.
describe("fieldNameFromServerError", () => {
  const fields = FORM.fields.map((field) => ({ name: field.name, label: field.label }));

  it("「라벨」: … 꼴이면 그 라벨의 칸 이름이다 — 실측 문장 그대로", () => {
    expect(fieldNameFromServerError("「평균선 기간」: 5일~120일 범위여야 합니다 (받은 값 3일)", fields)).toBe("period");
  });

  it("폼에 없는 라벨이면 null — 엉뚱한 칸을 빨갛게 하지 않는다", () => {
    expect(fieldNameFromServerError("「없는 칸」: 숫자여야 합니다", fields)).toBeNull();
  });

  it("라벨 없이 온 문장은 null — 토스트만 남는다", () => {
    expect(fieldNameFromServerError("봇 이름이 겹칩니다", fields)).toBeNull();
    expect(fieldNameFromServerError("", fields)).toBeNull();
  });
});
