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

  // 다전략 문구는 열자마자 화면에 뜨는 안내와 **같은 문장**이어야 한다 — 화면이 그 둘을
  // 문자열로 맞대 「이미 있는 말인가」를 판정하기 때문이다(판정은 화면이 한다, 여기가 아니라).
  it("다전략 문구가 열자마자 뜨는 안내와 한 글자까지 같다", () => {
    const count = 2;
    const shownOnOpen =
      `이 봇에는 전략이 ${count}개 실려 있는데 이 화면은 하나만 다룹니다. ` +
      "여기서 저장하면 나머지가 지워지므로 저장을 막아 뒀습니다.";
    expect(blockingSaveReason(draft("봇"), true, count)?.message).toBe(shownOnOpen);
  });

  it("이름이 먼저다 — 둘 다 어긋나도 고칠 수 있는 것을 먼저 말한다", () => {
    expect(blockingSaveReason(draft(""), false, 0)?.field).toBe("bot_nm");
  });

  it("다 갖추면 막지 않는다", () => {
    expect(blockingSaveReason(draft("봇"), true, 1)).toBeNull();
  });
});
