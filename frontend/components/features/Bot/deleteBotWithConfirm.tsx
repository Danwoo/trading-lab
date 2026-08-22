"use client";

import { showMessage, showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { deleteBot } from "@/services/bot/botService";

/**
 * 봇 삭제 — 되돌릴 수 없으므로 **무엇이 함께 사라지고 무엇이 남는지**를 먼저 말한다.
 *
 * 두 결과가 다르므로 한 문장으로 뭉치지 않는다:
 * - 실린 전략(`tn_bot_strategy`)은 FK 의 `ON DELETE CASCADE` 로 함께 사라진다.
 * - 검증 실행(`tn_backtest_run.bot_id`)은 FK 가 아예 없어(0015_backtest) 막지도 지우지도
 *   않는다 — 행은 남고 `bot_id` 만 가리킬 곳을 잃는다.
 *
 * 이 두 사실이 문구의 근거이고, 어긋나면
 * `backend-service/tests/test_bot_delete_cascade_boundary.py` 가 잡는다.
 *
 * 반환값은 「지웠나」다 — 취소·실패는 false 라, 호출부가 그때만 목록을 고치면 된다.
 */
export async function deleteBotWithConfirm(bot: { bot_id: number; bot_nm: string }): Promise<boolean> {
  const confirmed = await showMessage(
    "봇 삭제",
    <div className="flex flex-col gap-2">
      <p>「{bot.bot_nm}」 봇을 지웁니다. 되돌릴 수 없습니다.</p>
      <ul className="list-disc pl-4">
        <li>이 봇에 실린 전략과 그 설정이 함께 지워집니다.</li>
        <li>이미 돌린 검증 기록은 남지만, 어느 봇의 것인지 가리키지 못하게 됩니다.</li>
      </ul>
    </div>,
    { type: "confirm", confirmText: "삭제", cancelText: "취소", confirmButtonType: "danger" },
  );
  if (!confirmed) return false;

  try {
    const result = await deleteBot(bot.bot_id);
    if (result === null) {
      showToast("봇을 지우지 못했습니다.", "error");
      return false;
    }
    showToast(result.message ?? "봇을 지웠습니다.", "success");
    return true;
  } catch (error) {
    showToast(getApiErrorMessage(error), "error");
    return false;
  }
}
