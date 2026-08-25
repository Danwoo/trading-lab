"use client";

import { WRITE_DENIED_SHORT, canWriteWithAuthor } from "@/constants/writeAccess";
import { useSessionContext } from "@/hooks/shared/useSessionContext";

export interface WriteAccess {
  /** 저장·실행 조작부를 살려도 되는가. 세션을 아직 못 읽었으면 `true`(아래 주석 참조). */
  canWrite: boolean;
  /** 권한이 없어 막혔음이 **확정**됐는가. 배너·사유 문구는 이 값으로만 낸다. */
  isDenied: boolean;
  /** 조작부 `title` 설명에 그대로 넣는 한 줄. 막히지 않았으면 `undefined`. */
  deniedHint: string | undefined;
}

/**
 * 「이 계정이 저장·실행을 할 수 있는가」 — 화면이 벽을 **누르기 전에** 말하기 위한 자리 (#341).
 *
 * **이것은 방어가 아니라 설명이다.** 방어는 backend `require_role` 이 한다(그쪽은 fail-closed).
 * 그래서 세션을 읽는 중(`isLoaded === false`)에는 막지 않는다 — 여기서 fail-closed 로 잠그면
 * 권한이 있는 대다수가 매 진입마다 「막힘 → 열림」 깜빡임을 본다. 아직 모르는 것을 「막혔다」고
 * 말하지 않는 것은 이 레포가 이미 지키는 규칙이다(`IngestConsole` 의 「소스를 확인하는 중입니다」).
 */
export function useWriteAccess(): WriteAccess {
  const { authorId, isLoaded } = useSessionContext();
  const isDenied = isLoaded && !canWriteWithAuthor(authorId);
  return {
    canWrite: !isDenied,
    isDenied,
    deniedHint: isDenied ? WRITE_DENIED_SHORT : undefined,
  };
}
