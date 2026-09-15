// #453 F1 — 봇 저장 실패가 1.6초 만에 사라지고, 어느 칸인지도 안 짚었다.
//
// 판정을 한 곳으로 모으면 화면이 그것을 **남길 수 있다**. 이 그물은 무엇이 막고 무엇을 짚는지
// 본다 — 문구는 화면 쪽 그물이 따로 재고, 여기서는 「어느 칸인가」와 순서를 잡는다.
import { describe, expect, it } from "vitest";

import { blockingSaveReason } from "@/lib/bot/saveGuard";

const draft = (bot_nm: string) => ({ bot_nm });

describe("저장을 막는 이유", () => {
  it("이름이 비면 그 칸을 짚는다 — 긴 폼에서 어디를 고칠지가 답이다", () => {
    expect(blockingSaveReason(draft(""), true, 1)).toEqual({ field: "bot_nm", message: "봇 이름을 적어주세요." });
  });

  it("공백만 친 것도 빈 이름이다", () => {
    expect(blockingSaveReason(draft("   "), true, 1)?.field).toBe("bot_nm");
  });

  it("전략이 없으면 막지만 짚을 칸은 없다", () => {
    const blocked = blockingSaveReason(draft("봇"), false, 0);
    expect(blocked?.field).toBeNull();
    expect(blocked?.message).toContain("전략을 하나 고르면");
  });

  it("전략이 여럿 실린 봇은 나머지를 지우지 않으려고 막는다 — 몇 개인지 말한다", () => {
    const blocked = blockingSaveReason(draft("봇"), true, 3);
    expect(blocked?.message).toContain("3개");
    expect(blocked?.message).toContain("나머지가 지워지므로");
  });

  // 다전략 문구는 **열자마자 이미 화면에 있다**(`BotWorkbench` 의 `loadError`). 저장할 때 또
  // 얹으면 한 자리가 같은 말을 두 번 한다 — 그래서 「이미 보이는 말」이라고 표시해 보낸다.
  it("다전략은 이미 화면에 있다고 표시한다 — 같은 말을 두 번 하지 않으려고", () => {
    expect(blockingSaveReason(draft("봇"), true, 2)?.alreadyShown).toBe(true);
    expect(blockingSaveReason(draft(""), true, 1)?.alreadyShown).toBeUndefined();
  });

  it("이름이 먼저다 — 둘 다 어긋나도 고칠 수 있는 것을 먼저 말한다", () => {
    expect(blockingSaveReason(draft(""), false, 0)?.field).toBe("bot_nm");
  });

  it("다 갖추면 막지 않는다", () => {
    expect(blockingSaveReason(draft("봇"), true, 1)).toBeNull();
  });
});
