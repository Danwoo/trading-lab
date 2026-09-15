import type { BotDraft } from "@/components/features/Bot/botFormModel";

/** 저장을 막는 이유 하나 — 칸을 짚을 수 있으면 `field` 가 그 이름이다. */
export interface SaveBlock {
  field: string | null;
  message: string;
  /**
   * 이 말이 **이미 화면에 있는가.** 다전략 봇은 열자마자 같은 문장이 뜨므로(`loadError`),
   * 저장할 때 또 얹으면 한 자리가 같은 말을 두 번 한다 — 이 레포가 이름 붙인 결함이다(B-20).
   */
  alreadyShown?: boolean;
}

/**
 * 저장 전에 화면이 스스로 막는 것들 — **판정을 한 곳에 둔다.**
 *
 * 종전에는 `handleSave` 안에 세 갈래가 흩어져 각자 토스트만 띄우고 돌아갔다. 토스트는 1.6초
 * 뒤 사라지고 폼은 열 칸이 넘어, **2초 뒤 화면에는 실패했다는 흔적이 없다** — 스크롤을 내려
 * 저장을 눌렀다면 위로 올라가 이름 칸을 찾아야 하는데 그때는 문구가 이미 없다 (#453 F1).
 *
 * 같은 셸의 격자 폼은 폼 안에 문구를 남긴다. 두 폼이 실패를 다르게 다루던 것을 맞춘다.
 */
export function blockingSaveReason(
  draft: Pick<BotDraft, "bot_nm">,
  hasStrategy: boolean,
  loadedStrategyCount: number,
): SaveBlock | null {
  if (draft.bot_nm.trim() === "") {
    return { field: "bot_nm", message: "봇 이름을 적어주세요." };
  }
  if (!hasStrategy) {
    return { field: null, message: "전략을 하나 고르면 저장할 수 있습니다." };
  }
  if (loadedStrategyCount > 1) {
    return {
      field: null,
      // 문장을 `loadError` 와 맞춘다 — 두 자리가 다른 말을 하면 같은 사실이 둘로 읽힌다.
      message:
        `이 봇에는 전략이 ${loadedStrategyCount}개 실려 있는데 이 화면은 하나만 다룹니다. ` +
        "여기서 저장하면 나머지가 지워지므로 저장을 막아 뒀습니다.",
      alreadyShown: true,
    };
  }
  return null;
}
